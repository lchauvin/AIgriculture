"""Pydantic request/response schemas for the AIgriculture API.

Versioned under ``/api/v1`` per the URL routing in
:mod:`aigriculture.api.routes`. Add v2 schemas next to these when a
breaking change is needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

# A bounding box in EPSG:4326: (minx, miny, maxx, maxy) i.e.
# (west_lon, south_lat, east_lon, north_lat).
BBox = Annotated[
    tuple[float, float, float, float],
    Field(description="(minx, miny, maxx, maxy) in EPSG:4326"),
]


# ---- enums ------------------------------------------------------------------


class JobStatus(str, Enum):
    """Lifecycle of a backend job."""

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class GAEZClass(str, Enum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    N = "N"


# ---- requests ---------------------------------------------------------------


class EnvelopeRequest(BaseModel):
    """POST /api/v1/envelope body.

    Compute Tier 1 climatic-envelope suitability for a region against the
    Quebec staples catalogue. Historical-only for the MVP; SSP-projection
    support lands once we wire CanDCS-M6 into the runner.
    """

    model_config = ConfigDict(extra="forbid")

    bbox: BBox
    historical_years: tuple[int, ...] = Field(
        default=(2017, 2018, 2019),
        min_length=1,
        description="Calendar years to pull AgERA5 historical climate for.",
    )
    crops: tuple[str, ...] | None = Field(
        default=None,
        description=(
            "Optional subset of crop IDs from the catalogue. "
            "Defaults to every crop in data/crops/quebec_staples.yaml."
        ),
    )

    @model_validator(mode="after")
    def _check_bbox(self) -> "EnvelopeRequest":
        minx, miny, maxx, maxy = self.bbox
        if not (-180 <= minx < maxx <= 180):
            raise ValueError(
                f"bbox longitude must be -180 ≤ minx < maxx ≤ 180; got {self.bbox}"
            )
        if not (-90 <= miny < maxy <= 90):
            raise ValueError(
                f"bbox latitude must be -90 ≤ miny < maxy ≤ 90; got {self.bbox}"
            )
        # Keep MVP bbox area sane — a 5°×5° window is roughly 250k km²,
        # plenty for a Quebec sub-region and still cheap to compute.
        if (maxx - minx) > 5.0 or (maxy - miny) > 5.0:
            raise ValueError(
                "bbox is too large for the MVP (>5° per side). "
                "Pick a smaller region or contact us to lift the limit."
            )
        return self


# ---- envelope result --------------------------------------------------------


class CropEnvelopeScore(BaseModel):
    """One crop's region-mean envelope outcome."""

    crop_id: str
    scientific_name: str
    common_name_en: str
    common_name_fr: str | None = None

    envelope_score: Annotated[float, Field(ge=0.0, le=1.0)]
    preference_score: Annotated[float, Field(ge=0.0, le=1.0)]
    combined_score: Annotated[float, Field(ge=0.0, le=1.0)]

    gaez_class: GAEZClass = Field(
        description="GAEZ S1-S4-N class of the *envelope* score (preserves the GAEZ semantics)."
    )

    limiting_factor: str | None = Field(
        default=None,
        description=(
            "Modal limiting factor across the region "
            "(temperature, gdd, precipitation, growing_season, soil_ph). "
            "None when no cells were limited."
        ),
    )

    per_factor_envelope: dict[str, float] = Field(
        default_factory=dict,
        description="Per-factor envelope sub-scores (region-mean).",
    )


class ProvenanceStamp(BaseModel):
    source: str
    version: str
    fingerprint: str
    license: str
    citation_key: str


class EnvelopeResult(BaseModel):
    """The job's payload when status == succeeded."""

    bbox: BBox
    historical_years: tuple[int, ...]
    crops: list[CropEnvelopeScore]
    provenance: list[ProvenanceStamp] = Field(
        default_factory=list,
        description="One stamp per data source consumed for traceability.",
    )

    @model_validator(mode="after")
    def _sort_crops_by_score(self) -> "EnvelopeResult":
        # Always return crops ranked best→worst by combined score. The
        # frontend never has to worry about sort order.
        object.__setattr__(
            self,
            "crops",
            sorted(self.crops, key=lambda c: -c.combined_score),
        )
        return self


# ---- job status responses --------------------------------------------------


class JobAccepted(BaseModel):
    """202 response body when a job is queued."""

    job_id: UUID = Field(default_factory=uuid4)
    status: Literal[JobStatus.pending] = JobStatus.pending
    poll_url: str


class JobView(BaseModel):
    """GET /api/v1/jobs/{id} body — full job state."""

    job_id: UUID
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: EnvelopeResult | None = None

    @model_validator(mode="after")
    def _exclusive_states(self) -> "JobView":
        if self.status == JobStatus.succeeded and self.result is None:
            raise ValueError("succeeded job must have a result")
        if self.status == JobStatus.failed and not self.error:
            raise ValueError("failed job must have an error message")
        if self.status in (JobStatus.pending, JobStatus.running) and (
            self.result is not None or self.error is not None
        ):
            raise ValueError("in-flight job must not have a result or error")
        return self


__all__ = [
    "BBox",
    "CropEnvelopeScore",
    "EnvelopeRequest",
    "EnvelopeResult",
    "GAEZClass",
    "JobAccepted",
    "JobStatus",
    "JobView",
    "ProvenanceStamp",
]


# ---- helpers used by both schemas + runner ---------------------------------


def utcnow() -> datetime:
    """UTC `now`. Module-level so tests can monkeypatch it."""
    return datetime.now(timezone.utc)
