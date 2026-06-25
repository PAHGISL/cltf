#!/usr/bin/env python3
"""
Script: test_contracts.py
Objective: Verify CLTF workbench data contracts and package-path configuration.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Workbench contract and configuration modules.
Outputs: Pytest assertions.
Usage: python -m pytest apps/herbicide_workbench/tests/test_contracts.py -q
Dependencies: pandas, workbench
"""

from __future__ import annotations

import sys

import pandas as pd

from workbench.contracts import (
    AssessmentResult,
    CaseSelection,
    ExternalInputs,
    PreparedInputs,
    RunResult,
)


def test_case_selection_contains_site_soil_and_herbicide() -> None:
    case = CaseSelection("NSW_Griffith", "Heavy", "Imazapic")

    assert case.site_id == "NSW_Griffith"
    assert case.soil_group == "Heavy"
    assert case.herbicide == "Imazapic"


def test_config_points_to_python_src() -> None:
    from workbench.config import CLTF_SRC, REPO_ROOT

    assert CLTF_SRC == REPO_ROOT / "python" / "src"
    assert (CLTF_SRC / "cltf" / "__init__.py").exists()


def test_ensure_cltf_path_adds_python_src() -> None:
    from workbench.config import CLTF_SRC, ensure_cltf_path

    src_text = str(CLTF_SRC)
    while src_text in sys.path:
        sys.path.remove(src_text)

    ensure_cltf_path()

    assert sys.path[0] == src_text


def test_run_contracts_hold_prepared_inputs_and_assessment() -> None:
    case = CaseSelection("NSW_Griffith", "Heavy", "Imazapic")
    forcing = pd.DataFrame({"time_days": [0], "cumulative_infiltration_mm": [0.0]})
    bulk_density = pd.DataFrame({"estimate_g_cm3": [1.43]})
    observations = pd.DataFrame({"analysis_concentration_ug_kg": [10.9]})
    external = ExternalInputs(
        forcing=forcing,
        bulk_density=bulk_density,
        soil_properties=pd.DataFrame({"property": ["SOC"]}),
        top_bulk_density_g_cm3=1.47,
        bottom_bulk_density_g_cm3=1.52,
        warnings=[],
        metadata={"source": "shared-cache"},
    )
    prepared = PreparedInputs(
        case=case,
        site={"site_id": "NSW_Griffith"},
        observations=observations,
        forcing=external.forcing,
        bulk_density=external.bulk_density,
        soil_properties=external.soil_properties,
        application_date=pd.Timestamp("2024-04-26"),
        application_rate_g_ha=24.0,
        top_bulk_density_g_cm3=external.top_bulk_density_g_cm3,
        bottom_bulk_density_g_cm3=external.bottom_bulk_density_g_cm3,
    )
    assessment = AssessmentResult(
        date=pd.Timestamp("2024-07-25"),
        time_days=90,
        concentration_top_ug_kg=4.2,
        concentration_bottom_ug_kg=0.4,
        resident_profile_fraction=0.62,
    )
    result = RunResult(
        parameters={"mu": 0.05},
        predictions=pd.DataFrame({"time_days": [0]}),
        fit=None,
        assessment=assessment,
        warnings=[],
        metadata={"case": case.site_id},
    )

    assert prepared.case == case
    assert result.assessment.time_days == 90
