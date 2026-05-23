"""Observed crop yields from Statistics Canada — Field Crop Reporting Series.

Table **32-10-0359-01** "Estimated areas, yield, production, average farm price
and total farm value of principal field crops, in metric and imperial units"
[@StatCanFCRS2026]. Provincial annual yields back to 1908, released under the
Statistics Canada Open Licence. This is AIgriculture's primary observed-yield
target for the Quebec hindcast (``docs/research/04-uncertainty-and-validation``
Part B).

The full table ships as a single ~5 MB zip whose CSV expands to ~60 MB. We
cache the extracted CSV under ``data/cache/statcan`` and parse only the slice
we need — one GEO × one crop × the "Average yield" disposition. The bulk file
is used (rather than the WDS vector API) so the harness holds the complete
historical record offline once cached.

Real-schema notes (verified against the 2026-03 release):

- The estimate dimension is named ``Harvest disposition``; the metric yield
  rows carry ``"Average yield (kilograms per hectare)"``.
- ``Type of crop`` for grain corn is exactly ``"Corn for grain"``.
- ``VALUE`` is in **kg/ha** (SCALAR_FACTOR "units"); we convert to t/ha.
- Each (GEO × crop × disposition) maps to a stable StatCan VECTOR — e.g.
  Quebec grain-corn yield is ``v115114112`` — handy for cross-checks.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "statcan"

TABLE_ID = "32-10-0359-01"
PRODUCT_ID = "32100359"
BULK_CSV_URL = f"https://www150.statcan.gc.ca/n1/tbl/csv/{PRODUCT_ID}-eng.zip"
CSV_NAME = f"{PRODUCT_ID}.csv"

# The ``Harvest disposition`` value carrying the metric yield estimate.
YIELD_DISPOSITION = "Average yield (kilograms per hectare)"

SOURCE_NAME = "Statistics Canada — Field Crop Reporting Series"
LICENSE = "Statistics Canada Open Licence"
CITATION_KEY = "StatCanFCRS2026"


@dataclass(frozen=True, slots=True)
class ObservedYieldSeries:
    """A single GEO × crop observed-yield time series, in t/ha.

    ``by_year`` maps calendar year → yield (t/ha). Years with a suppressed
    or missing StatCan value are simply absent from the mapping.
    """

    crop_label: str
    geo: str
    unit: str  # always "t/ha"
    by_year: dict[int, float]
    source: str
    table_id: str
    license: str
    citation_key: str

    def years(self) -> list[int]:
        return sorted(self.by_year)


class StatCanFCRSSource:
    """Loader for StatCan Table 32-10-0359-01 with a local CSV cache."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR

    @property
    def csv_path(self) -> Path:
        return self.cache_dir / CSV_NAME

    def _ensure_csv(self) -> Path:
        """Return the cached CSV path, downloading + extracting if absent."""
        if self.csv_path.exists():
            return self.csv_path
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Fixed StatCan HTTPS endpoint; not user-controlled.
        with urlopen(BULK_CSV_URL) as resp:  # noqa: S310
            blob = resp.read()
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            zf.extract(CSV_NAME, path=self.cache_dir)
        return self.csv_path

    def load_yield_t_ha(
        self, crop_label: str, geo: str = "Quebec"
    ) -> ObservedYieldSeries:
        """Observed average yield (t/ha) by year for one crop × geography.

        ``crop_label`` must match the StatCan ``Type of crop`` value exactly
        (e.g. ``"Corn for grain"``). Raises ``ValueError`` if the filter
        selects no rows — a guard against silently mismatched labels.
        """
        import pandas as pd

        csv = self._ensure_csv()
        df = pd.read_csv(
            csv,
            usecols=[
                "REF_DATE",
                "GEO",
                "Harvest disposition",
                "Type of crop",
                "UOM",
                "VALUE",
            ],
            dtype={"REF_DATE": "Int64", "VALUE": "float64"},
            encoding="utf-8-sig",  # strip the BOM on the first column name
        )
        mask = (
            (df["GEO"] == geo)
            & (df["Type of crop"] == crop_label)
            & (df["Harvest disposition"] == YIELD_DISPOSITION)
        )
        sub = df.loc[mask, ["REF_DATE", "VALUE"]].dropna()
        by_year = {
            int(row.REF_DATE): float(row.VALUE) / 1000.0  # kg/ha → t/ha
            for row in sub.itertuples(index=False)
        }
        if not by_year:
            raise ValueError(
                f"No StatCan yield rows for crop_label={crop_label!r}, "
                f"geo={geo!r}, disposition={YIELD_DISPOSITION!r}. Check the "
                f"exact 'Type of crop' / 'GEO' labels in {csv}."
            )
        return ObservedYieldSeries(
            crop_label=crop_label,
            geo=geo,
            unit="t/ha",
            by_year=by_year,
            source=SOURCE_NAME,
            table_id=TABLE_ID,
            license=LICENSE,
            citation_key=CITATION_KEY,
        )


__all__ = [
    "BULK_CSV_URL",
    "CITATION_KEY",
    "LICENSE",
    "ObservedYieldSeries",
    "SOURCE_NAME",
    "StatCanFCRSSource",
    "TABLE_ID",
    "YIELD_DISPOSITION",
]
