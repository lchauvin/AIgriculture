"""Data ingestion and access layer.

One submodule per provider (e.g. ``copernicus``, ``planetary_computer``,
``eccc``, ``aafc``, ``statcan``). The public surface of this package
abstracts over "stream from STAC" vs "load from local Zarr"; downstream
modules should never directly reach for an HTTP client or a file path.
"""
