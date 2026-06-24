#!/usr/bin/env python3
"""
Script: test_assessment.py
Objective: Verify CLTF residue assessment date selection and summaries.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Prediction-like pandas data frames and assessment dates.
Outputs: Pytest assertions for assessment helpers.
Usage: python -m pytest apps/herbicide_workbench/tests/test_assessment.py -q
Dependencies: pandas, pytest, workbench
"""

from __future__ import annotations

import pandas as pd
import pytest

from workbench.assessment import (
    assessment_date_from_preset,
    default_assessment_date,
    summarize_assessment,
    validate_assessment_date,
)


def test_default_assessment_is_90_days_after_application() -> None:
    application = pd.Timestamp("2024-04-26")
    available = pd.date_range(application, "2024-09-19")

    assert default_assessment_date(application, available) == pd.Timestamp(
        "2024-07-25"
    )


def test_default_assessment_is_capped_by_available_forcing() -> None:
    application = pd.Timestamp("2024-04-26")
    available = pd.date_range(application, "2024-05-10")

    assert default_assessment_date(application, available) == pd.Timestamp(
        "2024-05-10"
    )


def test_assessment_preset_cannot_exceed_observed_forcing() -> None:
    with pytest.raises(ValueError, match="observed climate"):
        assessment_date_from_preset(
            pd.Timestamp("2024-04-26"),
            400,
            pd.Timestamp("2024-09-19"),
        )


def test_assessment_cannot_exceed_observed_forcing() -> None:
    with pytest.raises(ValueError, match="observed climate"):
        validate_assessment_date(
            pd.Timestamp("2025-06-01"),
            pd.Timestamp("2024-04-26"),
            pd.Timestamp("2024-09-19"),
        )


def test_assessment_summary_selects_exact_prediction_row() -> None:
    predictions = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-04-26", "2024-07-25", "2024-09-19"]
            ),
            "time_days": [0, 90, 146],
            "concentration_top_ug_kg": [10.0, 3.0, 1.0],
            "concentration_bottom_ug_kg": [0.0, 0.5, 0.4],
            "mass_top": [1.0, 0.3, 0.1],
            "mass_bottom": [0.0, 0.2, 0.2],
        }
    )

    result = summarize_assessment(predictions, pd.Timestamp("2024-07-25"))

    assert result.time_days == 90
    assert result.concentration_top_ug_kg == 3.0
    assert result.concentration_bottom_ug_kg == 0.5
    assert result.resident_profile_fraction == 0.5
