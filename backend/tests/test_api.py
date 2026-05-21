"""Tests for the FastAPI backend.

Three concerns:

1. Pydantic schema validation — bbox bounds and exclusive-state rules.
2. Job store concurrency — a hammered store stays consistent.
3. Route integration via ``TestClient`` — the runner is replaced with a
   fake so tests stay deterministic and don't hit AgERA5 / SoilGrids.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from aigriculture.api import jobs as jobs_mod
from aigriculture.api import runner as runner_mod
from aigriculture.api.app import create_app
from aigriculture.api.jobs import JobStore
from aigriculture.api.schemas import (
    CropEnvelopeScore,
    EnvelopeRequest,
    EnvelopeResult,
    GAEZClass,
    JobStatus,
    JobView,
    ProvenanceStamp,
)


# ---- helpers ---------------------------------------------------------------


def _sample_request() -> EnvelopeRequest:
    return EnvelopeRequest(
        bbox=(-74.0, 45.0, -73.0, 46.0),
        historical_years=(2018,),
    )


def _sample_result(req: EnvelopeRequest) -> EnvelopeResult:
    return EnvelopeResult(
        bbox=req.bbox,
        historical_years=req.historical_years,
        crops=[
            CropEnvelopeScore(
                crop_id="corn_grain",
                scientific_name="Zea mays",
                common_name_en="Corn for Grain",
                common_name_fr="Maïs-grain",
                envelope_score=0.9,
                preference_score=0.7,
                combined_score=0.63,
                gaez_class=GAEZClass.S1,
                limiting_factor="temperature",
                per_factor_envelope={"temperature": 1.0, "gdd": 0.9},
            ),
        ],
        provenance=[
            ProvenanceStamp(
                source="agera5",
                version="2_0",
                fingerprint="deadbeef",
                license="CC-BY-4.0",
                citation_key="BoogaardAgERA5",
            ),
        ],
    )


# ---- schemas ---------------------------------------------------------------


class TestEnvelopeRequest:
    def test_basic_request_validates(self) -> None:
        req = EnvelopeRequest(bbox=(-74.0, 45.0, -73.0, 46.0))
        assert req.historical_years == (2017, 2018, 2019)
        assert req.crops is None

    def test_rejects_inverted_lon(self) -> None:
        with pytest.raises(ValueError, match="longitude"):
            EnvelopeRequest(bbox=(-73.0, 45.0, -74.0, 46.0))

    def test_rejects_inverted_lat(self) -> None:
        with pytest.raises(ValueError, match="latitude"):
            EnvelopeRequest(bbox=(-74.0, 46.0, -73.0, 45.0))

    def test_rejects_too_large_bbox(self) -> None:
        # 10°×10° → caught by the MVP cap (5° per side).
        with pytest.raises(ValueError, match="too large"):
            EnvelopeRequest(bbox=(-80.0, 40.0, -70.0, 50.0))


class TestJobView:
    def test_succeeded_must_have_result(self) -> None:
        with pytest.raises(ValueError, match="must have a result"):
            JobView(
                job_id=UUID(int=1),
                status=JobStatus.succeeded,
                created_at=dt.datetime.now(dt.timezone.utc),
                result=None,
            )

    def test_failed_must_have_error(self) -> None:
        with pytest.raises(ValueError, match="must have an error"):
            JobView(
                job_id=UUID(int=2),
                status=JobStatus.failed,
                created_at=dt.datetime.now(dt.timezone.utc),
                error=None,
            )

    def test_in_flight_must_not_have_result_or_error(self) -> None:
        with pytest.raises(ValueError, match="must not have"):
            JobView(
                job_id=UUID(int=3),
                status=JobStatus.pending,
                created_at=dt.datetime.now(dt.timezone.utc),
                error="oops",
            )


class TestEnvelopeResultSorting:
    def test_crops_sorted_by_combined_score_descending(self) -> None:
        req = _sample_request()
        crops = [
            CropEnvelopeScore(
                crop_id=f"crop_{i}",
                scientific_name="X y",
                common_name_en=f"Crop {i}",
                envelope_score=1.0,
                preference_score=score,
                combined_score=score,
                gaez_class=GAEZClass.S2,
            )
            for i, score in enumerate([0.3, 0.9, 0.6])
        ]
        res = EnvelopeResult(bbox=req.bbox, historical_years=req.historical_years, crops=crops)
        assert [c.combined_score for c in res.crops] == [0.9, 0.6, 0.3]


# ---- job store -------------------------------------------------------------


class TestJobStore:
    def test_create_returns_pending(self) -> None:
        store = JobStore()
        rec = store.create(_sample_request())
        view = store.get_view(rec.job_id)
        assert view is not None
        assert view.status == JobStatus.pending
        assert view.started_at is None

    def test_lifecycle_transitions(self) -> None:
        store = JobStore()
        rec = store.create(_sample_request())
        store.mark_started(rec.job_id)
        store.mark_succeeded(rec.job_id, _sample_result(rec.request))
        view = store.get_view(rec.job_id)
        assert view is not None
        assert view.status == JobStatus.succeeded
        assert view.result is not None and view.result.crops[0].crop_id == "corn_grain"
        assert view.started_at is not None
        assert view.completed_at is not None

    def test_failure_path(self) -> None:
        store = JobStore()
        rec = store.create(_sample_request())
        store.mark_started(rec.job_id)
        store.mark_failed(rec.job_id, "boom")
        view = store.get_view(rec.job_id)
        assert view is not None
        assert view.status == JobStatus.failed
        assert view.error == "boom"

    def test_concurrent_writes_dont_corrupt_state(self) -> None:
        store = JobStore()
        N = 100
        records = [store.create(_sample_request()) for _ in range(N)]
        errors: list[Exception] = []

        def worker(rec):  # noqa: ANN001
            try:
                store.mark_started(rec.job_id)
                time.sleep(0.001)
                store.mark_succeeded(rec.job_id, _sample_result(rec.request))
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(r,)) for r in records]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(store) == N
        for r in records:
            assert store.get_view(r.job_id).status == JobStatus.succeeded


# ---- routes / TestClient ---------------------------------------------------


@pytest.fixture
def app_with_fake_runner(monkeypatch):
    """Stand up a fresh FastAPI app whose runner is a fake that
    completes synchronously with a known result."""

    def fake_runner(job_id, store, **kwargs):  # noqa: ANN001
        store.mark_started(job_id)
        rec = store.get(job_id)
        if rec is None:
            return
        store.mark_succeeded(job_id, _sample_result(rec.request))

    # The envelope route imports run_envelope_job from
    # aigriculture.api.runner at import-time, then calls it via
    # ``background.add_task(run_envelope_job, ...)``. Patching the name
    # on the routes module is therefore what we need.
    from aigriculture.api.routes import envelope as envelope_route_mod

    monkeypatch.setattr(envelope_route_mod, "run_envelope_job", fake_runner)
    return create_app()


def test_health(app_with_fake_runner) -> None:
    client = TestClient(app_with_fake_runner)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "aigriculture"


def test_envelope_post_returns_202_and_job_id(app_with_fake_runner) -> None:
    client = TestClient(app_with_fake_runner)
    r = client.post(
        "/api/v1/envelope",
        json={
            "bbox": [-74.0, 45.0, -73.0, 46.0],
            "historical_years": [2018],
        },
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    job_id = body["job_id"]
    assert body["poll_url"] == f"/api/v1/jobs/{job_id}"


def test_envelope_post_invalid_bbox_returns_422(app_with_fake_runner) -> None:
    client = TestClient(app_with_fake_runner)
    r = client.post(
        "/api/v1/envelope",
        json={"bbox": [-73.0, 45.0, -74.0, 46.0]},  # inverted lon
    )
    assert r.status_code == 422


def test_full_post_then_poll_completes(app_with_fake_runner) -> None:
    """End-to-end: POST → 202 → GET poll_url → succeeded result."""
    client = TestClient(app_with_fake_runner)
    r1 = client.post(
        "/api/v1/envelope",
        json={"bbox": [-74.0, 45.0, -73.0, 46.0], "historical_years": [2018]},
    )
    assert r1.status_code == 202
    poll = r1.json()["poll_url"]

    # TestClient runs BackgroundTasks synchronously after the response,
    # so by the time we poll, the fake runner has finished.
    r2 = client.get(poll)
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "succeeded"
    assert body["result"]["crops"][0]["crop_id"] == "corn_grain"
    assert body["result"]["crops"][0]["gaez_class"] == "S1"


def test_unknown_job_returns_404(app_with_fake_runner) -> None:
    client = TestClient(app_with_fake_runner)
    r = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_runner_marks_failed_on_exception(monkeypatch) -> None:
    """If the inner compute throws, the runner must catch it and mark
    the job failed rather than crashing the worker."""
    store = JobStore()
    rec = store.create(_sample_request())

    def boom(*_args, **_kwargs):  # noqa: ANN001, ANN002
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(runner_mod, "_compute_envelope", boom)
    runner_mod.run_envelope_job(rec.job_id, store)

    view = store.get_view(rec.job_id)
    assert view is not None
    assert view.status == JobStatus.failed
    assert "synthetic failure" in (view.error or "")
