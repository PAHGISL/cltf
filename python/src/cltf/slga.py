#!/usr/bin/env python3
"""
Script: slga.py
Objective: Retrieve, normalize, and depth-weight SLGA whole-earth bulk density.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Coordinates, TERN API key, normalized cache, or manual overrides.
Outputs: Standard bulk-density bands and weighted estimates in g/cm3.
Usage: Import public functions from cltf or cltf.slga.
Dependencies: datetime, json, os, pathlib, re, urllib, numpy, pandas, requests
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import requests


JsonReader = Callable[[str], object]
_REQUIRED_COLUMNS = [
    "depth_top_mm",
    "depth_bottom_mm",
    "estimate_g_cm3",
    "lower_g_cm3",
    "upper_g_cm3",
    "source",
]


def _standard_depths() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "depth_top_mm": [0.0, 50.0, 150.0],
            "depth_bottom_mm": [50.0, 150.0, 300.0],
        }
    )


def _validate_bands(bands: pd.DataFrame) -> pd.DataFrame:
    missing = set(_REQUIRED_COLUMNS).difference(bands.columns)
    if missing:
        raise ValueError(
            f"Bulk-density data are missing columns: {', '.join(sorted(missing))}"
        )
    result = bands.loc[:, _REQUIRED_COLUMNS].copy()
    numeric_columns = [column for column in _REQUIRED_COLUMNS if column != "source"]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if not np.all(np.isfinite(result[numeric_columns].to_numpy(dtype=float))):
        raise ValueError("Bulk-density values and depths must be finite")
    if np.any(result["depth_bottom_mm"] <= result["depth_top_mm"]):
        raise ValueError("Bulk-density depth bands must have positive thickness")
    result["source"] = result["source"].astype(str)
    return result.sort_values("depth_top_mm", kind="stable").reset_index(drop=True)


def parse_slga_bulk_density(path: str | Path) -> pd.DataFrame:
    """Parse a normalized SLGA bulk-density JSON cache."""

    cache_path = Path(path)
    if not cache_path.exists():
        raise FileNotFoundError(f"SLGA cache does not exist: {cache_path}")
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    values = payload.get("values") if isinstance(payload, Mapping) else None
    if not isinstance(values, list):
        raise ValueError("SLGA cache does not contain a tabular values field")
    table = pd.DataFrame(values)
    source = (
        table["source"].astype(str)
        if "source" in table
        else pd.Series("SLGA whole-earth bulk density", index=table.index)
    )
    bands = pd.DataFrame(
        {
            "depth_top_mm": pd.to_numeric(
                table.get("depth_top_cm"),
                errors="coerce",
            )
            * 10.0,
            "depth_bottom_mm": pd.to_numeric(
                table.get("depth_bottom_cm"),
                errors="coerce",
            )
            * 10.0,
            "estimate_g_cm3": pd.to_numeric(
                table.get("estimate_g_cm3"),
                errors="coerce",
            ),
            "lower_g_cm3": pd.to_numeric(
                table.get("lower_g_cm3"),
                errors="coerce",
            ),
            "upper_g_cm3": pd.to_numeric(
                table.get("upper_g_cm3"),
                errors="coerce",
            ),
            "source": source,
        }
    )
    return _validate_bands(bands)


def weight_bulk_density(
    bands: pd.DataFrame,
    depth_top_mm: float,
    depth_bottom_mm: float,
) -> pd.DataFrame:
    """Calculate overlap-weighted bulk density for one target interval."""

    normalized = _validate_bands(bands)
    if (
        not math.isfinite(depth_top_mm)
        or not math.isfinite(depth_bottom_mm)
        or depth_bottom_mm <= depth_top_mm
    ):
        raise ValueError(
            "Target depth interval must have positive finite thickness"
        )
    overlap = np.maximum(
        0.0,
        np.minimum(normalized["depth_bottom_mm"], depth_bottom_mm)
        - np.maximum(normalized["depth_top_mm"], depth_top_mm),
    )
    thickness = depth_bottom_mm - depth_top_mm
    if abs(float(overlap.sum()) - thickness) > 1e-8:
        raise ValueError(
            "Bulk-density bands do not fully cover the requested depth interval"
        )

    def weighted(column: str) -> float:
        return float(np.sum(normalized[column] * overlap) / thickness)

    return pd.DataFrame(
        {
            "depth_top_mm": [depth_top_mm],
            "depth_bottom_mm": [depth_bottom_mm],
            "estimate_g_cm3": [weighted("estimate_g_cm3")],
            "lower_g_cm3": [weighted("lower_g_cm3")],
            "upper_g_cm3": [weighted("upper_g_cm3")],
            "source": ["; ".join(pd.unique(normalized["source"]))],
        }
    )


def _normalize_override(
    manual_override: float | Sequence[float] | pd.DataFrame,
) -> pd.DataFrame:
    if isinstance(manual_override, pd.DataFrame):
        return _validate_bands(manual_override)
    values = np.atleast_1d(np.asarray(manual_override, dtype=float))
    if len(values) not in (1, 3):
        raise ValueError(
            "manual_override must be one value, three standard-band values, "
            "or a data frame"
        )
    if len(values) == 1:
        values = np.repeat(values, 3)
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError(
            "Manual bulk-density values must be finite and positive"
        )
    result = _standard_depths()
    result["estimate_g_cm3"] = values
    result["lower_g_cm3"] = values
    result["upper_g_cm3"] = values
    result["source"] = "manual_override"
    return result


def _coordinate_tag(value: float) -> str:
    prefix = "m" if value < 0 else "p"
    return f"{prefix}{abs(value):.2f}".replace(".", "p")


def _cache_path(cache_dir: Path, latitude: float, longitude: float) -> Path:
    return cache_dir / (
        "slga_bulk_density_"
        f"{_coordinate_tag(latitude)}_{_coordinate_tag(longitude)}.json"
    )


def _query_url(endpoint: str, query: Mapping[str, object]) -> str:
    return (
        "https://esoil.io/TERNLandscapes/RasterProductsAPI/"
        f"{endpoint}?{urlencode(query)}"
    )


def _find_tables(value: object) -> list[pd.DataFrame]:
    if isinstance(value, pd.DataFrame):
        return [value]
    if isinstance(value, Mapping):
        tables: list[pd.DataFrame] = []
        if value and all(
            isinstance(item, (list, tuple, pd.Series, np.ndarray))
            for item in value.values()
        ):
            try:
                tables.append(pd.DataFrame(value))
            except ValueError:
                pass
        for item in value.values():
            tables.extend(_find_tables(item))
        return tables
    if isinstance(value, (list, tuple)):
        tables = []
        if value and all(isinstance(item, Mapping) for item in value):
            tables.append(pd.DataFrame(value))
        for item in value:
            tables.extend(_find_tables(item))
        return tables
    return []


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _product_table(payload: object) -> pd.DataFrame:
    candidates = _find_tables(payload)
    if not candidates:
        raise ValueError(
            "SLGA ProductInfo response contains no tabular product records"
        )
    scores = [
        sum(
            any(token in _normalize_name(str(column)) for token in ("cog", "path", "url", "model"))
            for column in candidate.columns
        )
        for candidate in candidates
    ]
    return candidates[int(np.argmax(scores))].copy()


def _match_column(
    table: pd.DataFrame,
    aliases: Sequence[str],
    required: bool = True,
) -> str | None:
    normalized = {
        _normalize_name(str(column)): str(column)
        for column in table.columns
    }
    for alias in aliases:
        match = normalized.get(_normalize_name(alias))
        if match is not None:
            return match
    if required:
        raise ValueError(
            f"SLGA ProductInfo response is missing: {' / '.join(aliases)}"
        )
    return None


def _select_products(payload: object) -> pd.DataFrame:
    products = _product_table(payload)
    cog_column = _match_column(
        products,
        (
            "COGPath",
            "COGsPath",
            "COG",
            "CloudOptimizedGeoTIFF",
            "URL",
            "FilePath",
        ),
    )
    component_column = _match_column(
        products,
        ("Component", "ComponentName", "Statistic"),
        required=False,
    )
    model_column = _match_column(
        products,
        ("Model", "ModelName", "ModelID", "RasterName"),
        required=False,
    )
    cog_path = products[cog_column].astype(str)
    model_text = (
        cog_path
        if model_column is None
        else products[model_column].astype(str) + " " + cog_path
    )
    component_text = (
        model_text
        if component_column is None
        else products[component_column].astype(str) + " " + model_text
    ).str.lower()

    rows: list[dict[str, object]] = []
    for index, text in model_text.items():
        match = re.search(r"([0-9]{3})[_-]([0-9]{3})", text)
        if match is None:
            continue
        depth_top_mm, depth_bottom_mm = (
            10.0 * float(match.group(1)),
            10.0 * float(match.group(2)),
        )
        statistic_text = component_text.loc[index]
        statistic = (
            "lower_g_cm3"
            if re.search(r"lower|_05_|p05", statistic_text)
            else (
                "upper_g_cm3"
                if re.search(r"upper|_95_|p95", statistic_text)
                else "estimate_g_cm3"
            )
        )
        rows.append(
            {
                "depth_top_mm": depth_top_mm,
                "depth_bottom_mm": depth_bottom_mm,
                "statistic": statistic,
                "cog_path": cog_path.loc[index],
                "depth_key": f"{depth_top_mm:g}_{depth_bottom_mm:g}",
            }
        )
    selected = pd.DataFrame(rows)
    if selected.empty:
        raise ValueError("SLGA ProductInfo did not resolve standard depth bands")
    selected = selected.loc[
        selected["depth_key"].isin(("0_50", "50_150", "150_300"))
        & selected["cog_path"].str.len().gt(0)
    ].drop_duplicates(["depth_key", "statistic"])
    if len(selected) != 9:
        raise ValueError(
            "SLGA ProductInfo did not resolve all three estimates for "
            "three depth bands"
        )
    return selected.reset_index(drop=True)


def _extract_numeric_value(payload: object) -> float:
    if isinstance(payload, (int, float, np.number)) and math.isfinite(float(payload)):
        return float(payload)
    if isinstance(payload, pd.DataFrame):
        payload = payload.to_dict(orient="list")
    if isinstance(payload, Mapping):
        normalized = {
            _normalize_name(str(key)): value
            for key, value in payload.items()
        }
        for preferred in (
            "value",
            "rastervalue",
            "pixelvalue",
            "bandvalue",
            "result",
        ):
            if preferred in normalized:
                try:
                    return _extract_numeric_value(normalized[preferred])
                except ValueError:
                    pass
        for value in payload.values():
            try:
                return _extract_numeric_value(value)
            except ValueError:
                pass
    elif isinstance(payload, (list, tuple, np.ndarray, pd.Series)):
        for value in payload:
            try:
                return _extract_numeric_value(value)
            except ValueError:
                pass
    raise ValueError("SLGA Drill response contains no numeric raster value")


def _read_cog(
    cog_path: str,
    latitude: float,
    longitude: float,
    api_key: str,
) -> float:
    try:
        import rasterio
    except ImportError as error:
        raise RuntimeError(
            "SLGA Drill failed and optional package 'rasterio' is "
            "unavailable for COG fallback"
        ) from error

    with rasterio.Env(GDAL_HTTP_HEADERS=f"x-api-key: {api_key}"):
        with rasterio.open(cog_path) as raster:
            value = next(raster.sample([(longitude, latitude)]))[0]
    if not np.isfinite(value):
        raise ValueError("SLGA COG contains no value at the requested point")
    return float(value)


def _read_product_value(
    product: pd.Series,
    latitude: float,
    longitude: float,
    api_key: str,
    drill_reader: JsonReader,
) -> float:
    url = _query_url(
        "Drill",
        {
            "format": "json",
            "verbose": "false",
            "TERNapiKey": api_key,
            "COGPath": product["cog_path"],
            "latitude": f"{latitude:g}",
            "longitude": f"{longitude:g}",
        },
    )
    try:
        return _extract_numeric_value(drill_reader(url))
    except Exception:
        return _read_cog(
            str(product["cog_path"]),
            latitude,
            longitude,
            api_key,
        )


def _read_json(url: str) -> object:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return response.json()


def _write_cache(
    path: Path,
    latitude: float,
    longitude: float,
    bands: pd.DataFrame,
) -> None:
    values = []
    for row in bands.itertuples(index=False):
        values.append(
            {
                "depth_top_cm": row.depth_top_mm / 10.0,
                "depth_bottom_cm": row.depth_bottom_mm / 10.0,
                "estimate_g_cm3": row.estimate_g_cm3,
                "lower_g_cm3": row.lower_g_cm3,
                "upper_g_cm3": row.upper_g_cm3,
                "source": row.source,
            }
        )
    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "attribute": "Bulk Density (whole earth)",
        "units": "g/cm3",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "values": values,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def fetch_slga_bulk_density(
    latitude: float,
    longitude: float,
    cache_dir: str | Path,
    manual_override: float | Sequence[float] | pd.DataFrame | None = None,
    refresh: bool = False,
    api_key: str | None = None,
    metadata_reader: JsonReader = _read_json,
    drill_reader: JsonReader = _read_json,
) -> pd.DataFrame:
    """Retrieve standard SLGA whole-earth bulk-density depth bands."""

    if manual_override is not None:
        return _normalize_override(manual_override)
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("SLGA coordinates must be finite")

    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    cache_path = _cache_path(directory, latitude, longitude)
    if not refresh and cache_path.exists():
        result = parse_slga_bulk_density(cache_path)
        result.attrs["cache_path"] = str(cache_path)
        return result

    resolved_key = api_key or os.getenv("TERN_API_KEY", "")
    if not resolved_key:
        raise ValueError("TERN_API_KEY is required for an SLGA cache miss")
    metadata_url = _query_url(
        "ProductInfo",
        {
            "format": "json",
            "attribute": "Bulk Density (whole earth)",
            "product": "SLGA",
            "isCurrentVersion": "1",
        },
    )
    products = _select_products(metadata_reader(metadata_url))
    products["value"] = [
        _read_product_value(
            product,
            latitude,
            longitude,
            resolved_key,
            drill_reader,
        )
        for _, product in products.iterrows()
    ]

    bands = _standard_depths()
    bands["estimate_g_cm3"] = np.nan
    bands["lower_g_cm3"] = np.nan
    bands["upper_g_cm3"] = np.nan
    bands["source"] = (
        "credentialed SLGA v2 whole-earth bulk density retrieval"
    )
    for product in products.itertuples(index=False):
        mask = (
            bands["depth_top_mm"].eq(product.depth_top_mm)
            & bands["depth_bottom_mm"].eq(product.depth_bottom_mm)
        )
        bands.loc[mask, product.statistic] = product.value
    bands = _validate_bands(bands)
    _write_cache(cache_path, latitude, longitude, bands)
    bands.attrs["cache_path"] = str(cache_path)
    return bands
