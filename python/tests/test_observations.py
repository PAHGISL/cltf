#!/usr/bin/env python3
"""
Script: test_observations.py
Objective: Verify observation intervals, non-detects, summaries, and imports.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Fixed observation values and the source herbicide workbook.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_observations.py -q
Dependencies: numpy, pandas, pytest, openpyxl, cltf
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cltf.observations import (
    depth_interval_mm,
    geometric_concentration,
    infer_application_rate_g_ha,
    prepare_non_detects,
    read_herbicide_workbook,
)


def test_depth_intervals_and_non_detects() -> None:
    assert depth_interval_mm("SA", "10cm") == (0.0, 100.0)
    assert depth_interval_mm("NSW", "30cm") == (150.0, 300.0)
    prepared = prepare_non_detects(
        concentration_ug_kg=[2, 0, 0],
        is_non_detect=[False, True, False],
        detection_limit_ug_kg=[np.nan, 0.2, np.nan],
    )
    np.testing.assert_allclose(
        prepared["analysis_concentration_ug_kg"],
        [2, 0.1, np.nan],
        equal_nan=True,
    )
    assert prepared["lod_substituted"].tolist() == [False, True, False]
    assert prepared["excluded_zero"].tolist() == [False, False, True]


def test_geometric_summary_is_calculated_in_log_space() -> None:
    result = geometric_concentration(
        pd.DataFrame(
            {
                "group": ["a", "a", "a"],
                "analysis_concentration_ug_kg": [1.0, 2.0, 4.0],
            }
        ),
        group_columns=["group"],
    )
    assert result.loc[0, "n"] == 3
    assert result.loc[0, "geometric_mean_ug_kg"] == pytest.approx(2.0)


def test_application_rate_inference_reverses_concentration() -> None:
    result = infer_application_rate_g_ha(
        t0_concentration_ug_kg=[16.4, 16.4, 16.4],
        depth_top_mm=0,
        depth_bottom_mm=100,
        bulk_density_g_cm3=1.3,
    )
    assert result == pytest.approx(21.32)


def test_workbook_import_smoke() -> None:
    path = Path(
        "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx"
    )
    if not path.exists():
        pytest.skip("source workbook unavailable")

    result = read_herbicide_workbook(path, sheets=("SA", "NSW", "Qld"))
    assert result.shape == (1216, 24)
    assert result.iloc[0]["site_id"] == "NSW_Griffith"
    assert result.iloc[0]["sample_date"] == pd.Timestamp("2024-04-26")
    assert result["unit_status"].unique().tolist() == [
        "inferred_from_application_rate"
    ]
