"""POST /api/v1/envelope — dispatch a Tier 1 envelope job."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from ..jobs import JobStore
from ..runner import run_envelope_job
from ..schemas import EnvelopeRequest, JobAccepted

router = APIRouter(prefix="/api/v1", tags=["envelope"])


def get_store(request: Request) -> JobStore:
    """Lift the app-level singleton off ``app.state``.

    Tests can override this dependency to inject a fresh store, and the
    same hook makes it trivial to swap the in-memory store for a Redis
    or relational one later.
    """
    return request.app.state.job_store  # type: ignore[no-any-return]


@router.post(
    "/envelope",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a Tier 1 envelope computation",
    description=(
        "Validates the request, queues the work as a background job, and "
        "returns a job ID immediately. Poll ``GET /api/v1/jobs/{job_id}`` "
        "until ``status == 'succeeded'`` to retrieve the result."
    ),
)
def post_envelope(
    payload: EnvelopeRequest,
    background: BackgroundTasks,
    store: JobStore = Depends(get_store),
) -> JobAccepted:
    record = store.create(payload)
    background.add_task(run_envelope_job, record.job_id, store)
    return JobAccepted(
        job_id=record.job_id,
        poll_url=f"/api/v1/jobs/{record.job_id}",
    )
