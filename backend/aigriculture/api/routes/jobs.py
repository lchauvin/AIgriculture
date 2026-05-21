"""GET /api/v1/jobs/{job_id} — poll job state."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..jobs import JobStore
from ..schemas import JobView

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def get_store(request: Request) -> JobStore:
    return request.app.state.job_store  # type: ignore[no-any-return]


@router.get(
    "/jobs/{job_id}",
    response_model=JobView,
    summary="Get job status and (when done) result",
)
def get_job(job_id: UUID, store: JobStore = Depends(get_store)) -> JobView:
    view = store.get_view(job_id)
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return view
