"""In-memory job store for the AIgriculture API.

For the MVP we keep job state in a process-local dict guarded by a lock.
This is the right scope for a single-process FastAPI app driving local
compute. When we deploy and need horizontal scaling we'll swap the
:class:`JobStore` interface implementation for one backed by Redis
(per ADR 0004) or a relational store, keeping the API surface
unchanged.

The store is intentionally tiny — three operations: ``create``,
``mark_started``, ``mark_succeeded`` / ``mark_failed``, and ``get`` —
plus a ``with_lock`` context manager so the runner can read-modify-write
safely.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator
from uuid import UUID, uuid4

from .schemas import EnvelopeRequest, EnvelopeResult, JobStatus, JobView, utcnow


@dataclass
class _JobRecord:
    """The store's internal job representation."""

    job_id: UUID
    request: EnvelopeRequest
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    result: EnvelopeResult | None = None

    def to_view(self) -> JobView:
        return JobView(
            job_id=self.job_id,
            status=self.status,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            result=self.result,
        )


class JobStore:
    """Thread-safe in-memory job store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[UUID, _JobRecord] = {}

    # ---- mutation -----------------------------------------------------

    def create(self, request: EnvelopeRequest) -> _JobRecord:
        job_id = uuid4()
        record = _JobRecord(
            job_id=job_id,
            request=request,
            status=JobStatus.pending,
            created_at=utcnow(),
        )
        with self._lock:
            self._jobs[job_id] = record
        return record

    def mark_started(self, job_id: UUID) -> None:
        with self._lock:
            rec = self._require(job_id)
            rec.status = JobStatus.running
            rec.started_at = utcnow()

    def mark_succeeded(self, job_id: UUID, result: EnvelopeResult) -> None:
        with self._lock:
            rec = self._require(job_id)
            rec.status = JobStatus.succeeded
            rec.result = result
            rec.completed_at = utcnow()

    def mark_failed(self, job_id: UUID, error: str) -> None:
        with self._lock:
            rec = self._require(job_id)
            rec.status = JobStatus.failed
            rec.error = error
            rec.completed_at = utcnow()

    # ---- read ---------------------------------------------------------

    def get(self, job_id: UUID) -> _JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_view(self, job_id: UUID) -> JobView | None:
        with self._lock:
            rec = self._jobs.get(job_id)
            return rec.to_view() if rec is not None else None

    def iter_records(self) -> Iterator[_JobRecord]:
        """Iterate a snapshot of records — primarily for diagnostics."""
        with self._lock:
            snapshot = list(self._jobs.values())
        yield from snapshot

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)

    # ---- internals ----------------------------------------------------

    def _require(self, job_id: UUID) -> _JobRecord:
        rec = self._jobs.get(job_id)
        if rec is None:
            raise KeyError(f"Job {job_id} not found")
        return rec


__all__ = ["JobStore"]
