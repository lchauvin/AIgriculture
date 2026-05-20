"""AAFC Annual Crop Inventory — Google Earth Engine data source.

The AAFC Annual Crop Inventory (ACI) is the primary current-day crop map
for the Quebec MVP per ADR 0004. Annual 30 m (56 m for 2009–2010)
classification of Canadian land cover and crop types, ~90 classes, from
the Earth Observation Team at Agriculture and Agri-Food Canada.

- Earth Engine collection: ``AAFC/ACI``
- Coverage: 2009 – present (2024 is the latest year as of 2026-05)
- Bands: ``landcover`` (integer class code, see the EE catalog page for
  the full legend — wheat, soybean, corn, canola, mixedwood, water, etc.)
- License: OGL-Canada-2.0
- Citation: "Agriculture and Agri-Food Canada Annual Crop Inventory. {YEAR}"

Access pattern
--------------
We use Earth Engine as our compute layer (server-side filtering and
clipping) and pull a small per-year GeoTIFF for the requested Quebec
bounding box via ``Image.getDownloadURL``. Each year's TIFF is cached
locally so re-loads are free.

Earth Engine requires a one-time browser-based authentication that
writes credentials to ``~/.config/earthengine/credentials`` and a
Google Cloud project ID passed to ``ee.Initialize(project=...)``.

Quotas
------
``getDownloadURL`` is limited to ~32 MB per request. A 1° × 1° bbox at
30 m for the single ``landcover`` band is well under that. Larger
regions would need ``ee.batch.Export.image.toDrive`` or tile-and-merge.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Sequence

import xarray as xr

from .base import (
    BBox,
    DataSource,
    TimeRange,
    validate_bbox,
    validate_time_range,
)

EE_COLLECTION = "AAFC/ACI"
NATIVE_RESOLUTION_M = 30
OUTPUT_CRS = "EPSG:4326"
SOURCE_URL = (
    "https://developers.google.com/earth-engine/datasets/catalog/AAFC_ACI"
)
LICENSE = "OGL-Canada-2.0"
CITATION_KEY = "AAFCACI"

# Coverage as of 2026-05. ACI is reprocessed annually; the upper bound
# advances each year and a per-call check ``validate_year_available()``
# would be a Phase 4 polish.
COVERAGE_START = date(2009, 1, 1)
COVERAGE_END_KNOWN = date(2024, 12, 31)


# A pluggable callable: ``(year: int, bbox: BBox, dest: Path) -> None``.
# Production wires this to Earth Engine; tests inject a synthetic writer.
ImageFetcher = Callable[[int, BBox, Path], None]


class AAFCACISource(DataSource):
    """Earth Engine-backed loader for the AAFC Annual Crop Inventory.

    Parameters
    ----------
    cache_dir
        Local directory where per-year clipped GeoTIFFs are cached.
    ee_project
        Google Cloud project ID for ``ee.Initialize(project=...)``.
        Earth Engine requires this since 2024. Ignored when
        ``image_fetcher`` is provided (tests).
    image_fetcher
        Optional callable used in place of the live Earth Engine fetch.
        Signature: ``(year, bbox, dest_path) -> None``. The fetcher must
        write a valid GeoTIFF to ``dest_path``.
    """

    name = "aafc_aci"
    version = "2024"  # latest year known available; not a schema version
    backend = "stream"
    is_static = False
    source_url = SOURCE_URL
    license = LICENSE
    citation_key = CITATION_KEY

    def __init__(
        self,
        cache_dir: str | Path,
        ee_project: str | None = None,
        image_fetcher: ImageFetcher | None = None,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ee_project = ee_project
        self._fetcher = image_fetcher
        self._ee_initialized = False

    # ---- DataSource interface ------------------------------------------------

    @property
    def variables(self) -> tuple[str, ...]:
        return ("landcover",)

    @property
    def temporal_coverage(self) -> tuple[date, date | None]:
        return (COVERAGE_START, None)

    @property
    def spatial_resolution_deg(self) -> float:
        # 30 m on a Lambert-conformal grid; in EPSG:4326 this is ~0.00027°
        # at 45°N (we let GDAL/EE resample to whatever grid the caller's
        # downstream tier expects).
        return 0.00027

    @property
    def crs(self) -> str:
        return OUTPUT_CRS

    def load(
        self,
        bbox: BBox,
        time_range: TimeRange | None = None,
        variables: Sequence[str] | None = None,
    ) -> xr.Dataset:
        validate_bbox(bbox)
        validate_time_range(time_range)
        if time_range is None:
            raise ValueError(
                "AAFC ACI is time-varying; pass an explicit time_range "
                "covering the years you want (each year is a separate image)."
            )
        self._resolve_variables(variables)  # validate only
        years = _years_in_range(time_range)
        if not years:
            raise ValueError(
                f"time_range {time_range} contains no full calendar year "
                f"between {COVERAGE_START.year} and {COVERAGE_END_KNOWN.year}."
            )

        per_year_arrays: list[xr.DataArray] = []
        for year in years:
            fp = self._cache_path(year, bbox)
            if not fp.exists():
                self._fetch_year(year, bbox, fp)
            per_year_arrays.append(self._open_year_tiff(fp, year))

        landcover = (
            per_year_arrays[0]
            if len(per_year_arrays) == 1
            else xr.concat(per_year_arrays, dim="time")
        )
        ds = xr.Dataset({"landcover": landcover})
        ds.attrs["aigriculture.provenance"] = self.provenance(
            bbox=bbox, time_range=time_range, variables=("landcover",),
        ).fingerprint()
        ds.attrs["resolution_m_native"] = NATIVE_RESOLUTION_M
        return ds

    # ---- internals -----------------------------------------------------------

    def _resolve_variables(self, variables: Sequence[str] | None) -> list[str]:
        if variables is None:
            return ["landcover"]
        unknown = [v for v in variables if v != "landcover"]
        if unknown:
            raise ValueError(
                f"AAFC ACI exposes only the 'landcover' band; got {unknown!r}."
            )
        return list(variables)

    def _cache_path(self, year: int, bbox: BBox) -> Path:
        bbox_tag = "_".join(f"{x:+.2f}" for x in bbox).replace("+", "p").replace("-", "m")
        return self.cache_dir / f"aci_{year:04d}_{bbox_tag}.tif"

    def _fetch_year(self, year: int, bbox: BBox, dest: Path) -> None:
        if self._fetcher is not None:
            self._fetcher(year, bbox, dest)
            return
        self._ensure_ee_initialized()
        # Lazy import — only needed when a real EE fetch runs.
        import ee  # noqa: PLC0415

        img = (
            ee.ImageCollection(EE_COLLECTION)
            .filter(ee.Filter.calendarRange(year, year, "year"))
            .first()
        )
        region = ee.Geometry.Rectangle(list(bbox), proj=OUTPUT_CRS, geodesic=False)
        url = img.getDownloadURL(
            {
                "region": region,
                "crs": OUTPUT_CRS,
                "scale": NATIVE_RESOLUTION_M,
                "format": "GEO_TIFF",
            }
        )
        _stream_url_to_path(url, dest)

    def _ensure_ee_initialized(self) -> None:
        if self._ee_initialized:
            return
        if self._ee_project is None:
            raise RuntimeError(
                "AAFCACISource needs an Earth Engine project ID. Pass "
                "ee_project='your-gcp-project' to the constructor, or "
                "provide an image_fetcher for offline / test use."
            )
        import ee  # noqa: PLC0415

        ee.Initialize(project=self._ee_project)
        self._ee_initialized = True

    @staticmethod
    def _open_year_tiff(fp: Path, year: int) -> xr.DataArray:
        import rioxarray as rxr  # noqa: PLC0415

        da = rxr.open_rasterio(fp, masked=True)
        # The ACI GeoTIFF carries one band; drop the band dim and attach a
        # time coordinate stamped at January 1 of the inventory year.
        if "band" in da.dims and da.sizes["band"] == 1:
            da = da.isel(band=0).drop_vars("band", errors="ignore")
        timestamp = xr.DataArray(
            data=[__import__("numpy").datetime64(f"{year:04d}-01-01")],
            dims="time",
        )
        return da.expand_dims(time=timestamp)


# ---- helpers ----------------------------------------------------------------


def _years_in_range(time_range: TimeRange) -> list[int]:
    """Return the calendar years covered by ``time_range``, intersected
    with the ACI coverage window."""
    start, end = time_range
    first = max(start.year, COVERAGE_START.year)
    last = min(end.year, COVERAGE_END_KNOWN.year)
    if first > last:
        return []
    return list(range(first, last + 1))


def _stream_url_to_path(url: str, dest: Path) -> None:
    """Download ``url`` to ``dest``. Used for Earth Engine getDownloadURL."""
    import urllib.request  # noqa: PLC0415

    with urllib.request.urlopen(url, timeout=300) as resp, dest.open("wb") as f:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)


__all__ = [
    "AAFCACISource",
    "COVERAGE_END_KNOWN",
    "COVERAGE_START",
    "EE_COLLECTION",
]
