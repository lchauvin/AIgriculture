"""Crop environmental requirements — load and validate the YAML catalogue.

The schema is hand-curated (per ADR 0003 §C). One entry per crop, with
trapezoidal-function bounds for temperature, precipitation, soil pH, and
growing-degree days; cycle-length bounds for the growing season; a kill
temperature for frost; and an audit trail of citations per parameter.

The YAML is loaded once into immutable Pydantic models and used by
``aigriculture.suitability.envelope`` to score gridded suitability maps.

Trapezoidal bounds convention
-----------------------------
All four-number bounds use the same ordering::

    absolute_min  <  optimal_min  <=  optimal_max  <  absolute_max

The Pydantic validators enforce this so a malformed YAML row will fail
at load time rather than at score time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrapezoidBounds(BaseModel):
    """The four numbers that define a trapezoidal membership function."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    absolute_min: float
    optimal_min: float
    optimal_max: float
    absolute_max: float

    @model_validator(mode="after")
    def _check_ordered(self) -> "TrapezoidBounds":
        if not (self.absolute_min < self.optimal_min):
            raise ValueError(
                f"absolute_min ({self.absolute_min}) must be < optimal_min "
                f"({self.optimal_min})"
            )
        if not (self.optimal_min <= self.optimal_max):
            raise ValueError(
                f"optimal_min ({self.optimal_min}) must be <= optimal_max "
                f"({self.optimal_max})"
            )
        if not (self.optimal_max < self.absolute_max):
            raise ValueError(
                f"optimal_max ({self.optimal_max}) must be < absolute_max "
                f"({self.absolute_max})"
            )
        return self


class TemperatureRequirements(BaseModel):
    """Mean growing-season temperature window (°C)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tmean_absolute_min_c: float
    tmean_optimal_min_c: float
    tmean_optimal_max_c: float
    tmean_absolute_max_c: float

    @model_validator(mode="after")
    def _check_ordered(self) -> "TemperatureRequirements":
        bounds = (
            self.tmean_absolute_min_c,
            self.tmean_optimal_min_c,
            self.tmean_optimal_max_c,
            self.tmean_absolute_max_c,
        )
        if list(bounds) != sorted(bounds) or self.tmean_absolute_min_c == self.tmean_absolute_max_c:
            raise ValueError(
                f"Temperature bounds must be strictly increasing; got {bounds}"
            )
        return self

    def as_trapezoid(self) -> TrapezoidBounds:
        return TrapezoidBounds(
            absolute_min=self.tmean_absolute_min_c,
            optimal_min=self.tmean_optimal_min_c,
            optimal_max=self.tmean_optimal_max_c,
            absolute_max=self.tmean_absolute_max_c,
        )


class GddRequirements(BaseModel):
    """Growing-degree-day window (°C·day) at a crop-specific base T."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_temperature_c: float
    absolute_min: float
    optimal_min: float
    optimal_max: float
    absolute_max: float

    @model_validator(mode="after")
    def _check_ordered(self) -> "GddRequirements":
        bounds = (self.absolute_min, self.optimal_min, self.optimal_max, self.absolute_max)
        if list(bounds) != sorted(bounds) or self.absolute_min == self.absolute_max:
            raise ValueError(f"GDD bounds must be strictly increasing; got {bounds}")
        return self

    def as_trapezoid(self) -> TrapezoidBounds:
        return TrapezoidBounds(
            absolute_min=self.absolute_min,
            optimal_min=self.optimal_min,
            optimal_max=self.optimal_max,
            absolute_max=self.absolute_max,
        )


class PrecipitationRequirements(BaseModel):
    """Annual precipitation window (mm)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    annual_absolute_min_mm: float
    annual_optimal_min_mm: float
    annual_optimal_max_mm: float
    annual_absolute_max_mm: float

    @model_validator(mode="after")
    def _check_ordered(self) -> "PrecipitationRequirements":
        bounds = (
            self.annual_absolute_min_mm,
            self.annual_optimal_min_mm,
            self.annual_optimal_max_mm,
            self.annual_absolute_max_mm,
        )
        if list(bounds) != sorted(bounds):
            raise ValueError(
                f"Precipitation bounds must be non-decreasing; got {bounds}"
            )
        return self

    def as_trapezoid(self) -> TrapezoidBounds:
        return TrapezoidBounds(
            absolute_min=self.annual_absolute_min_mm,
            optimal_min=self.annual_optimal_min_mm,
            optimal_max=self.annual_optimal_max_mm,
            absolute_max=self.annual_absolute_max_mm,
        )


class SoilRequirements(BaseModel):
    """Soil pH (H2O) window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ph_absolute_min: float
    ph_optimal_min: float
    ph_optimal_max: float
    ph_absolute_max: float

    @model_validator(mode="after")
    def _check_ordered(self) -> "SoilRequirements":
        bounds = (
            self.ph_absolute_min,
            self.ph_optimal_min,
            self.ph_optimal_max,
            self.ph_absolute_max,
        )
        if list(bounds) != sorted(bounds):
            raise ValueError(f"pH bounds must be non-decreasing; got {bounds}")
        return self

    def as_trapezoid(self) -> TrapezoidBounds:
        return TrapezoidBounds(
            absolute_min=self.ph_absolute_min,
            optimal_min=self.ph_optimal_min,
            optimal_max=self.ph_optimal_max,
            absolute_max=self.ph_absolute_max,
        )


class GrowingSeason(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cycle_min_days: int
    cycle_max_days: int

    @model_validator(mode="after")
    def _check_ordered(self) -> "GrowingSeason":
        if self.cycle_min_days >= self.cycle_max_days:
            raise ValueError(
                f"cycle_min_days ({self.cycle_min_days}) must be < "
                f"cycle_max_days ({self.cycle_max_days})"
            )
        return self


class FrostTolerance(BaseModel):
    """Frost-tolerance temperatures (°C).

    ``kill_temperature_c`` is the temperature below which the crop is
    killed outright. ``reduced_growth_temperature_c`` (optional) is the
    lower bound at which the crop can still survive with reduced growth.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kill_temperature_c: float
    reduced_growth_temperature_c: float | None = None


class Preference(BaseModel):
    """Single-point preferred values per factor.

    The trapezoid bounds on each ``TemperatureRequirements`` /
    ``GddRequirements`` / etc. describe the *envelope* (where the crop
    can survive). The optima below describe *where the crop performs
    best* — a single peak inside that envelope. The two together define
    a triangular preference-score that peaks at the optimum and decays
    linearly to the envelope edges, used to rank crops that all sit
    inside their envelopes (see envelope.triangle).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tmean_preferred_c: float
    gdd_preferred: float
    annual_precip_preferred_mm: float
    ph_preferred: float | None = None


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    ecoport_code: int | None = None
    accessed_via: str | None = None
    accessed_url: str | None = None
    applies_to: list[str] = Field(default_factory=list)


class CropRequirements(BaseModel):
    """All requirements for a single crop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    scientific_name: str
    common_name_en: str
    common_name_fr: str | None = None
    ecoport_code: int | None = None
    aci_code: int | None = None

    temperature: TemperatureRequirements
    gdd: GddRequirements
    precipitation: PrecipitationRequirements
    soil: SoilRequirements
    growing_season: GrowingSeason
    frost: FrostTolerance
    preference: Preference | None = None
    photoperiod: Literal["short_day", "long_day", "neutral"] | None = None

    citations: list[Citation]


class CropCatalogue(BaseModel):
    """A loaded YAML catalogue of crop requirements."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int
    crops: list[CropRequirements]

    def by_id(self, crop_id: str) -> CropRequirements:
        for c in self.crops:
            if c.id == crop_id:
                return c
        raise KeyError(
            f"No crop with id {crop_id!r} in catalogue; available: "
            f"{[c.id for c in self.crops]}"
        )


# ---- Loading ----------------------------------------------------------------

DEFAULT_QUEBEC_STAPLES = (
    Path(__file__).resolve().parents[3] / "data" / "crops" / "quebec_staples.yaml"
)


def load_catalogue(path: str | Path | None = None) -> CropCatalogue:
    """Load and validate a crop-requirements YAML.

    Defaults to the project's Quebec-staples catalogue at
    ``data/crops/quebec_staples.yaml``.
    """
    p = Path(path) if path is not None else DEFAULT_QUEBEC_STAPLES
    if not p.exists():
        raise FileNotFoundError(f"Crop catalogue not found at {p}")
    with p.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return CropCatalogue.model_validate(raw)


__all__ = [
    "Citation",
    "CropCatalogue",
    "CropRequirements",
    "DEFAULT_QUEBEC_STAPLES",
    "FrostTolerance",
    "GddRequirements",
    "GrowingSeason",
    "Preference",
    "PrecipitationRequirements",
    "SoilRequirements",
    "TemperatureRequirements",
    "TrapezoidBounds",
    "load_catalogue",
]
