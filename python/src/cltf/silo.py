#!/usr/bin/env python3
"""
Script: silo.py
Objective: Retrieve and parse cached SILO point climate data.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Coordinates, date range, SILO credentials, and cache directory.
Outputs: Daily rainfall/temperature forcing and cache metadata.
Usage: Import public functions from cltf or cltf.silo.
Dependencies: datetime, json, os, pathlib, tempfile, urllib, pandas, requests
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from urllib.parse import urlencode

import pandas as pd
import requests


Downloader = Callable[[str, Path], object]


def round_silo_coordinate(value: float) -> float:
    """Round one coordinate to the SILO 0.05-degree grid."""

    if not math.isfinite(value):
        raise ValueError("value must be one finite coordinate")
    return round(value / 0.05) * 0.05


def parse_silo_csv(path: str | Path) -> pd.DataFrame:
    """Parse a SILO Data Drill CSV into standard CLTF forcing fields."""

    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"SILO CSV does not exist: {csv_path}")
    raw = pd.read_csv(csv_path, comment="#")

    def select(candidates: tuple[str, ...]) -> str:
        for candidate in candidates:
            if candidate in raw.columns:
                return candidate
        raise ValueError(
            "SILO CSV is missing required date, temperature, or rain columns"
        )

    date_column = select(("Date", "YYYYMMDD", "date"))
    tmax_column = select(("T.Max", "Tmax", "max_temp"))
    tmin_column = select(("T.Min", "Tmin", "min_temp"))
    rain_column = select(("Rain", "rain", "rain_mm"))
    date = pd.to_datetime(
        raw[date_column].astype(str),
        format="%Y%m%d",
        errors="coerce",
    )
    result = pd.DataFrame(
        {
            "date": date,
            "jdays": date.dt.dayofyear,
            "rain_mm": pd.to_numeric(raw[rain_column], errors="coerce"),
            "Tmax": pd.to_numeric(raw[tmax_column], errors="coerce"),
            "Tmin": pd.to_numeric(raw[tmin_column], errors="coerce"),
        }
    )
    if result.isna().any().any():
        raise ValueError("SILO CSV contains invalid or missing forcing values")
    result["jdays"] = result["jdays"].astype(int)
    return result.sort_values("date", kind="stable").reset_index(drop=True)


def _coordinate_tag(value: float) -> str:
    prefix = "m" if value < 0 else "p"
    digits = f"{abs(value):.2f}".replace(".", "p")
    return f"{prefix}{digits}"


def _cache_paths(
    cache_dir: Path,
    latitude: float,
    longitude: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[Path, Path]:
    stem = "_".join(
        (
            "silo",
            _coordinate_tag(latitude),
            _coordinate_tag(longitude),
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d"),
        )
    )
    return cache_dir / f"{stem}.csv", cache_dir / f"{stem}.json"


def _request_url(
    latitude: float,
    longitude: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    username: str,
    password: str,
) -> str:
    query = urlencode(
        {
            "username": username,
            "password": password,
            "start": start_date.strftime("%Y%m%d"),
            "finish": end_date.strftime("%Y%m%d"),
            "lat": f"{latitude:.2f}",
            "lon": f"{longitude:.2f}",
            "format": "csv",
            "comment": "RXN",
        }
    )
    return (
        "https://www.longpaddock.qld.gov.au/cgi-bin/silo/"
        f"DataDrillDataset.php?{query}"
    )


def _download(url: str, destination: Path) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    destination.write_bytes(response.content)


def fetch_silo_point(
    latitude: float,
    longitude: float,
    start_date: object,
    end_date: object,
    cache_dir: str | Path,
    refresh: bool = False,
    username: str | None = None,
    password: str | None = None,
    downloader: Downloader = _download,
) -> pd.DataFrame:
    """Retrieve a SILO point series, preferring an immutable local cache."""

    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("SILO coordinates must be finite")
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end) or end < start:
        raise ValueError("SILO date range is invalid")

    grid_latitude = round_silo_coordinate(latitude)
    grid_longitude = round_silo_coordinate(longitude)
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    csv_path, metadata_path = _cache_paths(
        directory,
        grid_latitude,
        grid_longitude,
        start,
        end,
    )

    if not refresh and csv_path.exists() and metadata_path.exists():
        result = parse_silo_csv(csv_path)
        result.attrs["cache_path"] = str(csv_path)
        result.attrs["metadata_path"] = str(metadata_path)
        return result

    resolved_username = username or os.getenv("SILO_USERNAME", "")
    resolved_password = password or os.getenv("SILO_PASSWORD", "")
    if not resolved_username or not resolved_password:
        raise ValueError(
            "SILO_USERNAME and SILO_PASSWORD are required for a cache miss"
        )

    url = _request_url(
        grid_latitude,
        grid_longitude,
        start,
        end,
        resolved_username,
        resolved_password,
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="silo-",
        suffix=".csv",
        dir=directory,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        downloader(url, temporary_path)
        parse_silo_csv(temporary_path)
        temporary_path.replace(csv_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    metadata = {
        "source": "SILO Data Drill API",
        "request_latitude": latitude,
        "request_longitude": longitude,
        "grid_latitude": grid_latitude,
        "grid_longitude": grid_longitude,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_cache_file": csv_path.name,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    result = parse_silo_csv(csv_path)
    result.attrs["cache_path"] = str(csv_path)
    result.attrs["metadata_path"] = str(metadata_path)
    return result
