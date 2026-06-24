#!/usr/bin/env python3
"""
Script: test_exports.py
Objective: Verify CLTF workbench export artifacts and provenance metadata.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Synthetic prepared inputs and run results.
Outputs: Pytest assertions for exported CSV and JSON artifacts.
Usage: python -m pytest apps/herbicide_workbench/tests/test_exports.py -q
Dependencies: json, pandas, workbench
"""

from __future__ import annotations

import json

import pandas as pd

from workbench.contracts import (
    AssessmentResult,
    CaseSelection,
    PreparedInputs,
    RunResult,
)
from workbench.exports import build_export_artifacts
from workbench.site_registry import get_site


def _prepared_inputs() -> PreparedInputs:
    application_date = pd.Timestamp("2024-04-26")
    observations = pd.DataFrame(
        {
            "sample_date": [application_date],
            "days_since_application": [0],
            "depth_top_mm": [0],
            "depth_bottom_mm": [150],
            "analysis_concentration_ug_kg": [10.0],
        }
    )
    forcing = pd.DataFrame(
        {
            "date": [application_date],
            "time_days": [0],
            "cumulative_infiltration_mm": [0.0],
        }
    )
    bulk_density = pd.DataFrame(
        {
            "depth_top_mm": [0.0],
            "depth_bottom_mm": [150.0],
            "estimate_g_cm3": [1.47],
            "lower_g_cm3": [1.3],
            "upper_g_cm3": [1.6],
            "source": ["test"],
        }
    )
    return PreparedInputs(
        case=CaseSelection("NSW_Griffith", "Heavy", "Imazapic"),
        site=get_site("NSW_Griffith"),
        observations=observations,
        forcing=forcing,
        bulk_density=bulk_density,
        application_date=application_date,
        application_rate_g_ha=220.0,
        top_bulk_density_g_cm3=1.47,
        bottom_bulk_density_g_cm3=1.55,
    )


def _run_result() -> RunResult:
    predictions = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-04-26", "2024-07-25"]),
            "time_days": [0, 90],
            "concentration_top_ug_kg": [10.0, 2.0],
            "concentration_bottom_ug_kg": [0.0, 0.4],
            "mass_top": [1.0, 0.2],
            "mass_bottom": [0.0, 0.1],
        }
    )
    return RunResult(
        parameters={"mu": 1.0, "sigma": 0.6, "R_top": 2.0, "R_bottom": 3.0, "k": 0.005},
        predictions=predictions,
        fit=None,
        assessment=AssessmentResult(
            date=pd.Timestamp("2024-07-25"),
            time_days=90,
            concentration_top_ug_kg=2.0,
            concentration_bottom_ug_kg=0.4,
            resident_profile_fraction=0.3,
        ),
        warnings=["example warning"],
        metadata={
            "climate_source": "committed_cache",
            "soil_source": "committed_cache",
            "application_rate_source": "test",
            "effective_porosity": 0.2,
        },
    )


def test_exports_include_provenance_and_assessment() -> None:
    artifacts = build_export_artifacts(_run_result(), _prepared_inputs(), "0.2.0")

    assert {
        "observations_prepared.csv",
        "climate_forcing.csv",
        "bulk_density.csv",
        "predictions.csv",
        "fit_parameters.csv",
        "fit_diagnostics.csv",
        "run_metadata.json",
    } <= artifacts.keys()
    metadata = json.loads(artifacts["run_metadata.json"])
    assert metadata["residue_assessment"]["time_days"] == 90
    assert metadata["selected_case"]["site_id"] == "NSW_Griffith"
    assert metadata["input_provenance"]["climate_source"] == "committed_cache"
