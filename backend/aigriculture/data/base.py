"""Abstract interface for AIgriculture data sources.

Every dataset in the catalogue (`docs/research/01-data-catalogue.md`) is exposed
to the rest of the pipeline through a `DataSource` implementation. Downstream
modules should never reach for an HTTP client, a CDS API key, or a file path —
they receive an `xarray.Dataset` and a `Provenance` object, and do not know
whether the data came from a local Zarr store or a streamed STAC catalogue.

The interface is deliberately small. Two concrete operations:

- `load(bbox, time_range, variables)` returns a lazy `xarray.Dataset` for the
  requested subset.
- `provenance(...)` returns a stable, hashable description of the request so a
  downstream computation can be stamped with what it consumed.

See ADR 0004 (compute and storage) for the rationale behind the
stream / local split.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Literal, Sequence

import xarray as xr

Backend = Literal["local", "stream"]
BBox = tuple[float, float, float, float]  # (minx, miny, maxx, maxy) in dataset CRS
TimeRange = tuple[date, date]              # inclusive on both ends


@dataclass(frozen=True, slots=True)
class Provenance:
    """Stamp describing a single `DataSource.load()` call.

    The fingerprint is a stable SHA-256 over the request payload (excluding
    `loaded_at`). Two `Provenance` objects with the same fingerprint describe
    the same logical subset; downstream caches key on the fingerprint.
    """

    source_name: str
    source_version: str
    bbox: BBox
    time_range: TimeRange
    variables: tuple[str, ...]
    backend: Backend
    source_url: str
    license: str
    citation_key: str
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def fingerprint(self) -> str:
        payload = {
            "source_name": self.source_name,
            "source_version": self.source_version,
            "bbox": list(self.bbox),
            "time_range": [self.time_range[0].isoformat(), self.time_range[1].isoformat()],
            "variables": list(self.variables),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        # asdict() preserves tuple types; emit JSON-friendly lists instead.
        d["bbox"] = list(self.bbox)
        d["time_range"] = [self.time_range[0].isoformat(), self.time_range[1].isoformat()]
        d["variables"] = list(self.variables)
        d["loaded_at"] = self.loaded_at.isoformat()
        d["fingerprint"] = self.fingerprint()
        return d


class DataSource(ABC):
    """Abstract gridded-data source returning `xarray.Dataset`."""

    name: str
    version: str
    backend: Backend
    source_url: str
    license: str
    citation_key: str

    @property
    @abstractmethod
    def variables(self) -> tuple[str, ...]:
        """All variables this source can provide."""

    @property
    @abstractmethod
    def temporal_coverage(self) -> tuple[date, date | None]:
        """`(start, end)`; `end is None` means "ongoing / present"."""

    @property
    @abstractmethod
    def spatial_resolution_deg(self) -> float:
        """Approximate spatial resolution in decimal degrees.

        For datasets in a projected CRS, this is the nominal degree-equivalent
        used for catalogue display; the authoritative grid spacing is on the
        loaded `xarray.Dataset`.
        """

    @property
    @abstractmethod
    def crs(self) -> str:
        """EPSG / authority string, e.g. ``"EPSG:4326"``."""

    @abstractmethod
    def load(
        self,
        bbox: BBox,
        time_range: TimeRange,
        variables: Sequence[str] | None = None,
    ) -> xr.Dataset:
        """Return a lazy `xarray.Dataset` for the requested subset.

        Implementations must:

        - clip to ``bbox`` in this source's CRS;
        - slice ``time_range`` inclusively on both ends;
        - default to all `variables` if `None` is passed;
        - return a `Dataset` whose chunks are `dask`-backed when feasible.
        """

    def provenance(
        self,
        bbox: BBox,
        time_range: TimeRange,
        variables: Sequence[str] | None = None,
    ) -> Provenance:
        vars_ = tuple(variables) if variables is not None else self.variables
        return Provenance(
            source_name=self.name,
            source_version=self.version,
            bbox=bbox,
            time_range=time_range,
            variables=vars_,
            backend=self.backend,
            source_url=self.source_url,
            license=self.license,
            citation_key=self.citation_key,
        )


def validate_bbox(bbox: BBox) -> None:
    """Raise `ValueError` if `bbox` is degenerate."""
    minx, miny, maxx, maxy = bbox
    if not (minx < maxx and miny < maxy):
        raise ValueError(f"Degenerate bbox: {bbox!r} — require minx<maxx and miny<maxy.")


def validate_time_range(time_range: TimeRange) -> None:
    """Raise `ValueError` if start > end."""
    start, end = time_range
    if start > end:
        raise ValueError(f"time_range start ({start}) is after end ({end}).")


__all__ = [
    "BBox",
    "Backend",
    "DataSource",
    "Provenance",
    "TimeRange",
    "validate_bbox",
    "validate_time_range",
]
