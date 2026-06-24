#!/usr/bin/env python3
"""
Script: test_plots.py
Objective: Verify CLTF workbench diagnostic plotting wrappers.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Synthetic CLTF forcing, prediction, simulation, profile, and soil tables.
Outputs: Pytest assertions for matplotlib figures and assessment markers.
Usage: MPLBACKEND=Agg python -m pytest apps/herbicide_workbench/tests/test_plots.py -q
Dependencies: numpy, pandas, pytest, matplotlib, workbench
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from workbench.plots import (
    plot_bulk_density,
    plot_climate_forcing,
    plot_mass_balance,
    plot_mass_fractions,
    plot_objective_profiles,
    plot_observed_fitted,
    plot_residuals,
)


def _assessment_lines(figure):
    return [
        line
        for axis in figure.axes
        for line in axis.lines
        if line.get_label() == "Residue assessment"
    ]


def _assert_assessment_line_at_day(figure, day: int = 90) -> None:
    assessment_lines = _assessment_lines(figure)

    assert assessment_lines
    assert assessment_lines[0].get_xdata()[0] == day


def _forcing() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_days": [0, 30, 60, 90, 120],
            "rain_mm": [0.0, 8.0, 0.0, 12.0, 1.0],
            "pet_mm": [2.0, 2.5, 2.2, 2.1, 2.0],
            "daily_infiltration_mm": [0.0, 5.5, 0.0, 9.9, 0.0],
            "cumulative_infiltration_mm": [0.0, 5.5, 5.5, 15.4, 15.4],
        }
    )


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "days_since_application": [0, 90, 120, 0, 90, 120],
            "depth_top_mm": [0, 0, 0, 150, 150, 150],
            "depth_bottom_mm": [150, 150, 150, 300, 300, 300],
            "analysis_concentration_ug_kg": [10.0, 3.1, 2.0, 0.2, 0.5, 0.4],
            "predicted_concentration_ug_kg": [10.1, 3.0, 1.9, 0.2, 0.45, 0.38],
            "log_residual": [-0.01, 0.03, 0.05, 0.0, 0.1, 0.05],
        }
    )


def _simulation() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_days": [0, 30, 60, 90, 120],
            "mass_top": np.linspace(1.0, 0.2, 5),
            "mass_bottom": np.linspace(0.0, 0.3, 5),
            "mass_below": np.linspace(0.0, 0.2, 5),
            "mass_degraded": np.linspace(0.0, 0.3, 5),
        }
    )


def _profile() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "parameter": ["mu_top", "mu_top", "mu_top"],
            "parameter_value": [20.0, 30.0, 40.0],
            "objective": [2.0, 1.0, 1.5],
        }
    )


def _bulk_density() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "depth_top_mm": [0.0, 50.0, 150.0],
            "depth_bottom_mm": [50.0, 150.0, 300.0],
            "estimate_g_cm3": [1.4, 1.5, 1.55],
            "lower_g_cm3": [1.3, 1.4, 1.45],
            "upper_g_cm3": [1.5, 1.6, 1.65],
        }
    )


def test_climate_forcing_marks_assessment_day() -> None:
    figure = plot_climate_forcing(_forcing(), assessment_day=90)

    _assert_assessment_line_at_day(figure)


def test_observed_fitted_marks_assessment_day() -> None:
    figure = plot_observed_fitted(_predictions(), assessment_day=90)

    _assert_assessment_line_at_day(figure)


def test_mass_fractions_marks_assessment_day() -> None:
    figure = plot_mass_fractions(_simulation(), assessment_day=90)

    _assert_assessment_line_at_day(figure)


def test_mass_balance_marks_assessment_day() -> None:
    figure = plot_mass_balance(_simulation(), assessment_day=90)

    _assert_assessment_line_at_day(figure)


def test_non_temporal_diagnostics_render_without_assessment_lines() -> None:
    residuals = plot_residuals(_predictions())
    objective = plot_objective_profiles(_profile())
    density = plot_bulk_density(_bulk_density())

    assert not _assessment_lines(residuals)
    assert not _assessment_lines(objective)
    assert not _assessment_lines(density)
