#!/usr/bin/env python3
"""
Script: test_model_service.py
Objective: Verify direct Python CLTF model orchestration for the workbench.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Synthetic prepared CLTF app inputs.
Outputs: Pytest assertions for fitted run results.
Usage: python -m pytest apps/herbicide_workbench/tests/test_model_service.py -q
Dependencies: pandas, workbench
"""

from __future__ import annotations

import pandas as pd

from workbench.contracts import CaseSelection, PreparedInputs
from workbench.model_service import default_parameters, fit_case
from workbench.site_registry import get_site


def prepared_inputs() -> PreparedInputs:
    application_date = pd.Timestamp("2024-04-26")
    times = [0, 30, 60, 90, 120]
    forcing = pd.DataFrame(
        {
            "date": [application_date + pd.Timedelta(days=day) for day in times],
            "time_days": times,
            "cumulative_infiltration_mm": [0.0, 15.0, 32.0, 50.0, 70.0],
        }
    )
    observations = pd.DataFrame(
        {
            "sample_date": [
                application_date,
                application_date + pd.Timedelta(days=30),
                application_date + pd.Timedelta(days=60),
                application_date + pd.Timedelta(days=90),
                application_date + pd.Timedelta(days=90),
            ],
            "days_since_application": [0, 30, 60, 90, 90],
            "depth_top_mm": [0, 0, 0, 0, 150],
            "depth_bottom_mm": [150, 150, 150, 150, 300],
            "analysis_concentration_ug_kg": [10.0, 7.5, 4.0, 2.0, 0.7],
            "is_t0": [True, False, False, False, False],
            "used_for_calibration": [False, True, True, True, True],
        }
    )
    bulk_density = pd.DataFrame(
        {
            "depth_top_mm": [0.0, 50.0, 150.0],
            "depth_bottom_mm": [50.0, 150.0, 300.0],
            "estimate_g_cm3": [1.4, 1.5, 1.55],
            "lower_g_cm3": [1.3, 1.4, 1.45],
            "upper_g_cm3": [1.5, 1.6, 1.65],
            "source": ["test", "test", "test"],
        }
    )
    soil_properties = pd.DataFrame(
        {
            "property": ["SOC", "Clay"],
            "depth_top_mm": [0.0, 0.0],
            "depth_bottom_mm": [300.0, 300.0],
            "estimate": [1.0, 32.0],
            "unit": ["%", "%"],
            "source": ["test", "test"],
        }
    )
    return PreparedInputs(
        case=CaseSelection("NSW_Griffith", "Heavy", "Imazapic"),
        site=get_site("NSW_Griffith"),
        observations=observations,
        forcing=forcing,
        bulk_density=bulk_density,
        soil_properties=soil_properties,
        application_date=application_date,
        application_rate_g_ha=220.0,
        top_bulk_density_g_cm3=1.47,
        bottom_bulk_density_g_cm3=1.55,
    )


def test_fit_uses_replicate_log_objective() -> None:
    result = fit_case(prepared_inputs(), default_parameters())

    assert result.fit is not None
    assert result.fit.objective < 1e6
    assert result.assessment.time_days == 90
    assert "transport_scales" in result.metadata
    assert set(result.parameters) == {"mu", "sigma", "R", "k"}
    assert "profile_simulation" in result.metadata
    assert {
        "date",
        "time_days",
        "concentration_top_ug_kg",
        "concentration_bottom_ug_kg",
    } <= set(result.predictions.columns)


def test_default_profile_parameter_bounds_match_model_review() -> None:
    settings = default_parameters()

    assert settings.lower == {
        "mu": 0.1,
        "sigma": 0.1,
        "R": 1.0,
        "k": 1e-5,
    }
    assert settings.upper == {
        "mu": 10.0,
        "sigma": 10.0,
        "R": 100.0,
        "k": 1e-1,
    }
