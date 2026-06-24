#!/usr/bin/env python3
"""
Script: exports.py
Objective: Build shared-schema CLTF workbench download artifacts.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: RunResult objects, PreparedInputs objects, and app version strings.
Outputs: Named CSV and JSON artifact strings for Streamlit downloads.
Usage: Import build_export_artifacts from workbench.exports.
Dependencies: dataclasses, hashlib, json, pandas, workbench
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from workbench.contracts import PreparedInputs, RunResult


def _csv_text(data: pd.DataFrame) -> str:
    return data.to_csv(index=False, na_rep="")


def _checksum_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, pd.DataFrame):
        return [_jsonable(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _parameter_table(result: RunResult) -> pd.DataFrame:
    if result.fit is None:
        return pd.DataFrame(
            {
                "parameter": list(result.parameters),
                "estimate": list(result.parameters.values()),
            }
        )
    return pd.DataFrame(
        {
            "parameter": list(result.parameters),
            "estimate": [result.parameters[name] for name in result.parameters],
            "lower": [result.fit.lower[name] for name in result.parameters],
            "upper": [result.fit.upper[name] for name in result.parameters],
            "bound_hit": [result.fit.bound_hit[name] for name in result.parameters],
        }
    )


def _diagnostics_table(result: RunResult) -> pd.DataFrame:
    if result.fit is None:
        return pd.DataFrame(
            columns=[
                "start_index",
                "objective",
                "convergence",
                "message",
            ]
        )
    diagnostics = result.fit.all_starts.copy()
    diagnostics["selected"] = diagnostics["start_index"].eq(result.fit.start_index)
    diagnostics["start_transport_scale_top"] = (
        diagnostics["start_mu"] * diagnostics["start_R_top"]
    )
    diagnostics["start_transport_scale_bottom"] = (
        diagnostics["start_mu"] * diagnostics["start_R_bottom"]
    )
    diagnostics["fitted_transport_scale_top"] = (
        diagnostics["fitted_mu"] * diagnostics["fitted_R_top"]
    )
    diagnostics["fitted_transport_scale_bottom"] = (
        diagnostics["fitted_mu"] * diagnostics["fitted_R_bottom"]
    )
    return diagnostics


def _profiles_table(result: RunResult) -> pd.DataFrame:
    profiles = result.metadata.get("objective_profiles")
    if isinstance(profiles, pd.DataFrame):
        return profiles
    return pd.DataFrame(
        columns=[
            "parameter",
            "parameter_value",
            "objective",
            "convergence",
            "message",
        ]
    )


def _metadata(
    result: RunResult,
    prepared: PreparedInputs,
    app_version: str,
    checksums: dict[str, str],
) -> dict[str, Any]:
    fit_metadata = {
        "objective": None,
        "convergence": None,
        "message": "",
        "bound_hits": {},
        "transport_scales": result.metadata.get("transport_scales", {}),
        "identifiability_note": result.metadata.get("identifiability_note", ""),
    }
    if result.fit is not None:
        fit_metadata.update(
            {
                "objective": result.fit.objective,
                "convergence": result.fit.convergence,
                "message": result.fit.message,
                "bound_hits": result.fit.bound_hit,
                "selected_start": result.fit.start_index,
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "software": {
            "app_version": app_version,
        },
        "selected_case": {
            "site_id": prepared.case.site_id,
            "soil_group": prepared.case.soil_group,
            "herbicide": prepared.case.herbicide,
        },
        "input_provenance": {
            "climate_source": result.metadata.get("climate_source", "unknown"),
            "soil_source": result.metadata.get("soil_source", "unknown"),
            "application_rate_source": result.metadata.get(
                "application_rate_source",
                "unknown",
            ),
        },
        "application_rate": {
            "value_g_ha": result.metadata.get(
                "application_rate_g_ha",
                prepared.application_rate_g_ha,
            ),
            "source": result.metadata.get("application_rate_source", "unknown"),
        },
        "model": {
            "target_quantity": "layer-average resident concentration",
            "effective_porosity": result.metadata.get("effective_porosity"),
            "top_bulk_density_g_cm3": prepared.top_bulk_density_g_cm3,
            "bottom_bulk_density_g_cm3": prepared.bottom_bulk_density_g_cm3,
            "top_thickness_mm": result.metadata.get("top_thickness_mm"),
            "bottom_thickness_mm": result.metadata.get("bottom_thickness_mm"),
            "degradation_clock": "total elapsed time",
            "convolution_method": result.metadata.get("convolution_method"),
            "convolution_steps": result.metadata.get("convolution_steps"),
        },
        "calibration": fit_metadata,
        "residue_assessment": result.assessment,
        "warnings": result.warnings,
        "input_checksums": checksums,
    }


def build_export_artifacts(
    result: RunResult,
    prepared: PreparedInputs,
    app_version: str,
) -> dict[str, str]:
    """Build downloadable shared-schema CLTF run artifacts."""

    artifacts = {
        "observations_prepared.csv": _csv_text(prepared.observations),
        "climate_forcing.csv": _csv_text(prepared.forcing),
        "bulk_density.csv": _csv_text(prepared.bulk_density),
        "predictions.csv": _csv_text(result.predictions),
        "fit_parameters.csv": _csv_text(_parameter_table(result)),
        "fit_diagnostics.csv": _csv_text(_diagnostics_table(result)),
        "objective_profiles.csv": _csv_text(_profiles_table(result)),
    }
    checksums = {
        name: _checksum_text(text)
        for name, text in artifacts.items()
        if name in {
            "observations_prepared.csv",
            "climate_forcing.csv",
            "bulk_density.csv",
        }
    }
    artifacts["run_metadata.json"] = (
        json.dumps(
            _jsonable(_metadata(result, prepared, app_version, checksums)),
            indent=2,
        )
        + "\n"
    )
    return artifacts
