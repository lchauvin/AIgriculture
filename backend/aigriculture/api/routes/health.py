"""Liveness probe."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from ... import __version__

router = APIRouter(prefix="/api/v1", tags=["health"])


class Health(BaseModel):
    status: str
    service: str
    version: str
    now: datetime


@router.get("/health", response_model=Health, summary="Liveness probe")
def get_health() -> Health:
    return Health(
        status="ok",
        service="aigriculture",
        version=__version__,
        now=datetime.now(timezone.utc),
    )
