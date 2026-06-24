#!/usr/bin/env python3
"""
Script: data_services.py
Objective: Prepare cache-first climate and soil inputs for the CLTF workbench.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared case directories, optional SILO credentials, and optional TERN API key.
Outputs: ExternalInputs containing forcing, bulk density, metadata, and warnings.
Usage: Import prepare_external_inputs from workbench.data_services.
Dependencies: json, os, pathlib, tempfile, pandas, cltf, workbench
"""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import tempfile

import pandas as pd

from workbench.config import ensure_cltf_path
from workbench.contracts import CaseSelection, ExternalInputs
from workbench.site_registry import case_input_dir, get_site

ensure_cltf_path()
from cltf import (  # noqa: E402
    daily_infiltration,
    parse_silo_csv,
    parse_slga_bulk_density,
    pet_from_temperature,
    weight_bulk_density,
)
import cltf.silo as silo_service  # noqa: E402
import cltf.slga as slga_service  # noqa: E402


def _environment(
    environment: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return os.environ if environment is None else environment


def _environment_value(
    environment: Mapping[str, str],
    key: str,
) -> str:
    return str(environment.get(key, "") or "").strip()


def _read_case_config(input_dir: Path) -> dict[str, object]:
    path = input_dir / "case.json"
    if not path.exists():
        raise FileNotFoundError(f"Shared CLTF case configuration does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Shared CLTF case configuration is invalid: {path}")
    return payload


def _runtime_cache_dir(
    environment: Mapping[str, str],
    case: CaseSelection,
) -> Path:
    configured = _environment_value(environment, "CLTF_WORKBENCH_CACHE_DIR")
    base_dir = Path(configured) if configured else Path(tempfile.gettempdir())
    directory = (
        base_dir
        / "cltf_workbench"
        / case.site_id.lower()
        / case.soil_group.lower()
        / case.herbicide.lower()
    )
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _date_range(
    case_config: Mapping[str, object],
) -> tuple[pd.Timestamp, pd.Timestamp]:
    application_date = pd.Timestamp(case_config["application_date"]).normalize()
    final_date = pd.Timestamp(case_config["final_date"]).normalize()
    if final_date < application_date:
        raise ValueError("Case final_date cannot be before application_date")
    return application_date, final_date


def _slice_forcing_to_case(
    forcing: pd.DataFrame,
    application_date: pd.Timestamp,
    final_date: pd.Timestamp,
) -> pd.DataFrame:
    result = forcing.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.loc[
        result["date"].between(application_date, final_date)
    ].reset_index(drop=True)
    expected_dates = pd.date_range(application_date, final_date, freq="D")
    if not result["date"].equals(pd.Series(expected_dates, name="date")):
        raise ValueError(
            "Climate forcing cache does not fully cover the selected case date range"
        )
    return result


def _committed_forcing(
    input_dir: Path,
    application_date: pd.Timestamp,
    final_date: pd.Timestamp,
) -> pd.DataFrame:
    return _slice_forcing_to_case(
        parse_silo_csv(input_dir / "silo.csv"),
        application_date,
        final_date,
    )


def _live_forcing(
    case: CaseSelection,
    site: Mapping[str, object],
    application_date: pd.Timestamp,
    final_date: pd.Timestamp,
    environment: Mapping[str, str],
) -> pd.DataFrame:
    return _slice_forcing_to_case(
        silo_service.fetch_silo_point(
            latitude=float(site["latitude"]),
            longitude=float(site["longitude"]),
            start_date=application_date,
            end_date=final_date,
            cache_dir=_runtime_cache_dir(environment, case),
            refresh=True,
            username=_environment_value(environment, "SILO_USERNAME"),
            password=_environment_value(environment, "SILO_PASSWORD"),
        ),
        application_date,
        final_date,
    )


def _prepare_forcing(
    forcing: pd.DataFrame,
    site: Mapping[str, object],
    case_config: Mapping[str, object],
    application_date: pd.Timestamp,
) -> pd.DataFrame:
    result = forcing.copy()
    irrigation_mm = float(case_config.get("irrigation_mm", 0.0))
    et_factor = float(case_config.get("et_factor", 1.0))
    result["time_days"] = (result["date"] - application_date).dt.days.astype(int)
    result["pet_mm"] = pet_from_temperature(
        result["jdays"].to_numpy(),
        result["Tmax"].to_numpy(),
        result["Tmin"].to_numpy(),
        latitude_deg=float(site["latitude"]),
    )
    result["irrigation_mm"] = irrigation_mm
    result["daily_infiltration_mm"] = daily_infiltration(
        result["rain_mm"].to_numpy(),
        result["pet_mm"].to_numpy(),
        irrigation_mm=result["irrigation_mm"].to_numpy(),
        et_factor=et_factor,
    )
    result["cumulative_infiltration_mm"] = result[
        "daily_infiltration_mm"
    ].cumsum()
    return result.loc[
        :,
        [
            "date",
            "time_days",
            "jdays",
            "rain_mm",
            "Tmax",
            "Tmin",
            "pet_mm",
            "irrigation_mm",
            "daily_infiltration_mm",
            "cumulative_infiltration_mm",
        ],
    ]


def _committed_bulk_density(input_dir: Path) -> pd.DataFrame:
    return parse_slga_bulk_density(input_dir / "bulk_density.json")


def _live_bulk_density(
    case: CaseSelection,
    site: Mapping[str, object],
    environment: Mapping[str, str],
) -> pd.DataFrame:
    return slga_service.fetch_slga_bulk_density(
        latitude=float(site["latitude"]),
        longitude=float(site["longitude"]),
        cache_dir=_runtime_cache_dir(environment, case),
        refresh=True,
        api_key=_environment_value(environment, "TERN_API_KEY"),
    )


def _weighted_estimate(
    bulk_density: pd.DataFrame,
    depth_top_mm: float,
    depth_bottom_mm: float,
) -> float:
    weighted = weight_bulk_density(
        bulk_density,
        depth_top_mm=depth_top_mm,
        depth_bottom_mm=depth_bottom_mm,
    )
    return float(weighted.loc[0, "estimate_g_cm3"])


def prepare_external_inputs(
    case: CaseSelection,
    environment: Mapping[str, str] | None = None,
    refresh_climate: bool = False,
    refresh_soil: bool = False,
) -> ExternalInputs:
    """Prepare climate forcing and bulk density for a selected app case."""

    env = _environment(environment)
    input_dir = case_input_dir(case)
    site = get_site(case.site_id)
    case_config = _read_case_config(input_dir)
    application_date, final_date = _date_range(case_config)
    warnings: list[str] = []
    metadata: dict[str, object] = {
        "case_input_dir": str(input_dir),
        "application_date": application_date.strftime("%Y-%m-%d"),
        "final_date": final_date.strftime("%Y-%m-%d"),
        "top_depth_mm": float(case_config["top_depth_mm"]),
        "bottom_depth_mm": float(case_config["bottom_depth_mm"]),
    }

    has_silo_credentials = (
        bool(_environment_value(env, "SILO_USERNAME"))
        and bool(_environment_value(env, "SILO_PASSWORD"))
    )
    if refresh_climate and has_silo_credentials:
        try:
            raw_forcing = _live_forcing(
                case,
                site,
                application_date,
                final_date,
                env,
            )
            metadata["climate_source"] = "silo_api"
        except Exception as error:
            warnings.append(
                "SILO refresh failed; fallback to committed cache "
                f"({type(error).__name__}: {error})."
            )
            raw_forcing = _committed_forcing(input_dir, application_date, final_date)
            metadata["climate_source"] = "committed_cache"
    else:
        if refresh_climate and not has_silo_credentials:
            warnings.append(
                "SILO refresh requested without credentials; fallback to committed cache."
            )
        raw_forcing = _committed_forcing(input_dir, application_date, final_date)
        metadata["climate_source"] = "committed_cache"

    has_tern_key = bool(_environment_value(env, "TERN_API_KEY"))
    if refresh_soil and has_tern_key:
        try:
            bulk_density = _live_bulk_density(case, site, env)
            metadata["soil_source"] = "slga_api"
        except Exception as error:
            warnings.append(
                "SLGA refresh failed; fallback to committed cache "
                f"({type(error).__name__}: {error})."
            )
            bulk_density = _committed_bulk_density(input_dir)
            metadata["soil_source"] = "committed_cache"
    else:
        if refresh_soil and not has_tern_key:
            warnings.append(
                "SLGA refresh requested without TERN_API_KEY; fallback to committed cache."
            )
        bulk_density = _committed_bulk_density(input_dir)
        metadata["soil_source"] = "committed_cache"

    top_depth = float(case_config["top_depth_mm"])
    bottom_depth = float(case_config["bottom_depth_mm"])
    forcing = _prepare_forcing(raw_forcing, site, case_config, application_date)
    top_bulk_density = _weighted_estimate(bulk_density, 0.0, top_depth)
    bottom_bulk_density = _weighted_estimate(bulk_density, top_depth, bottom_depth)

    metadata.update(
        {
            "silo_cache_file": str(input_dir / "silo.csv"),
            "bulk_density_cache_file": str(input_dir / "bulk_density.json"),
            "silo_grid_latitude": site.get("silo_latitude"),
            "silo_grid_longitude": site.get("silo_longitude"),
        }
    )

    return ExternalInputs(
        forcing=forcing,
        bulk_density=bulk_density,
        top_bulk_density_g_cm3=top_bulk_density,
        bottom_bulk_density_g_cm3=bottom_bulk_density,
        warnings=warnings,
        metadata=metadata,
    )
