#!/usr/bin/env python3
"""
Script: test_validation.py
Objective: Verify resident-concentration observation CSV validation.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Uploaded observation-like pandas data frames.
Outputs: Pytest assertions for prepared CLTF observation tables.
Usage: python -m pytest apps/herbicide_workbench/tests/test_validation.py -q
Dependencies: pandas, pytest, workbench
"""

from __future__ import annotations

import pandas as pd
import pytest

from workbench.site_registry import get_site
from workbench.validation import (
    ValidationError,
    list_cases,
    prepare_uploaded_observations,
)


def test_observation_csv_is_the_only_uploaded_table() -> None:
    raw = pd.DataFrame(
        {
            "sample_date": ["2024-04-26", "2024-05-06"],
            "depth_top_mm": [0, 0],
            "depth_bottom_mm": [150, 150],
            "concentration_ug_kg": [10.9, 5.1],
            "is_t0": [True, False],
        }
    )

    prepared = prepare_uploaded_observations(raw, get_site("NSW_Griffith"))

    assert "analysis_concentration_ug_kg" in prepared.columns
    assert prepared["days_since_application"].tolist() == [0, 10]
    assert prepared["site_id"].tolist() == ["NSW_Griffith", "NSW_Griffith"]
    assert prepared["used_for_calibration"].tolist() == [False, True]


def test_relative_concentration_schema_is_rejected() -> None:
    raw = pd.DataFrame({"relative_concentration": [1.0]})

    with pytest.raises(ValidationError, match="concentration_ug_kg"):
        prepare_uploaded_observations(raw, get_site("NSW_Griffith"))


@pytest.mark.parametrize("legacy_column", ["depth_mm", "concentration"])
def test_legacy_column_aliases_are_rejected(legacy_column: str) -> None:
    raw = pd.DataFrame(
        {
            "sample_date": ["2024-04-26"],
            "depth_top_mm": [0],
            "depth_bottom_mm": [150],
            "concentration_ug_kg": [10.9],
            "is_t0": [True],
            legacy_column: [10.9],
        }
    )

    with pytest.raises(ValidationError, match="legacy"):
        prepare_uploaded_observations(raw, get_site("NSW_Griffith"))


def test_detection_limit_substitution_is_preserved() -> None:
    raw = pd.DataFrame(
        {
            "sample_date": ["2024-04-26", "2024-05-06"],
            "depth_top_mm": [0, 150],
            "depth_bottom_mm": [150, 300],
            "concentration_ug_kg": [10.9, 0.0],
            "is_t0": [True, False],
            "is_non_detect": [False, True],
            "detection_limit_ug_kg": [pd.NA, 0.2],
        }
    )

    prepared = prepare_uploaded_observations(raw, get_site("NSW_Griffith"))

    assert prepared.loc[1, "analysis_concentration_ug_kg"] == 0.1
    assert bool(prepared.loc[1, "lod_substituted"])
    assert prepared.loc[1, "used_for_calibration"]


def test_sampling_intervals_can_be_arbitrary_within_selected_profile() -> None:
    raw = pd.DataFrame(
        {
            "sample_date": ["2024-04-26", "2024-06-25"],
            "depth_top_mm": [0, 50],
            "depth_bottom_mm": [100, 150],
            "concentration_ug_kg": [10.9, 2.4],
            "is_t0": [True, False],
        }
    )

    prepared = prepare_uploaded_observations(raw, get_site("NSW_Griffith"))

    assert prepared["depth_bottom_mm"].tolist() == [100, 150]
    assert prepared["used_for_calibration"].tolist() == [False, True]


def test_list_cases_returns_uploaded_or_default_case() -> None:
    raw = pd.DataFrame(
        {
            "sample_date": ["2024-04-26"],
            "depth_top_mm": [0],
            "depth_bottom_mm": [150],
            "concentration_ug_kg": [10.9],
            "is_t0": [True],
            "soil_group": ["Heavy"],
            "herbicide": ["Imazapic"],
        }
    )
    prepared = prepare_uploaded_observations(raw, get_site("NSW_Griffith"))

    assert [case.site_id for case in list_cases(prepared)] == ["NSW_Griffith"]
