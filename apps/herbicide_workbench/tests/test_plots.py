#!/usr/bin/env python3
"""
Script: test_plots.py
Objective: Verify CLTF workbench diagnostic plotting wrappers.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Synthetic CLTF forcing, prediction, simulation, profile, and soil tables.
Outputs: Pytest assertions for matplotlib figures and assessment markers.
Usage: MPLBACKEND=Agg python -m pytest apps/herbicide_workbench/tests/test_plots.py -q
Dependencies: numpy, pandas, pytest, matplotlib, workbench
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, QuadMesh

from workbench.plots import (
    configure_matplotlib,
    plot_bulk_density,
    plot_cumulative_infiltration,
    plot_observation_violin,
    plot_profile_curve,
    plot_simulation_heatmap,
    plot_soil_properties,
    plot_water_forcing,
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
            "concentration_top_ug_kg": [10.0, 6.0, 3.0, 1.5, 0.8],
            "concentration_bottom_ug_kg": [0.0, 0.4, 0.9, 1.0, 0.7],
            "mass_top": np.linspace(1.0, 0.2, 5),
            "mass_bottom": np.linspace(0.0, 0.3, 5),
            "mass_below": np.linspace(0.0, 0.2, 5),
            "mass_degraded": np.linspace(0.0, 0.3, 5),
        }
    )


def _profile_simulation() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time_days": [0, 0, 0, 60, 60, 60, 120, 120, 120],
            "depth_mm": [0.0, 150.0, 300.0] * 3,
            "concentration_ug_kg": [10.0, 0.0, 0.0, 4.0, 1.2, 0.2, 1.0, 2.5, 0.9],
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


def _soil_properties() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "property": ["SOC", "SOC", "Clay", "Clay"],
            "depth_top_mm": [0.0, 150.0, 0.0, 150.0],
            "depth_bottom_mm": [150.0, 300.0, 150.0, 300.0],
            "estimate": [1.1, 0.5, 32.0, 36.0],
            "unit": ["%", "%", "%", "%"],
            "source": ["demo", "demo", "demo", "demo"],
        }
    )


def test_configure_matplotlib_sets_arial() -> None:
    configure_matplotlib()

    assert plt.rcParams["font.family"] == ["Arial"]


def test_water_forcing_marks_assessment_day() -> None:
    figure = plot_water_forcing(_forcing(), assessment_day=90)

    _assert_assessment_line_at_day(figure)


def test_cumulative_infiltration_plot_uses_time_axis() -> None:
    figure = plot_cumulative_infiltration(_forcing())

    axis = figure.axes[0]
    assert not axis.patches
    assert axis.lines[0].get_xdata().tolist() == [0, 30, 60, 90, 120]
    assert "Cumulative infiltration" in axis.get_ylabel()


def test_observation_violin_has_jitter_dashed_fits_and_simulation_curves() -> None:
    figure = plot_observation_violin(
        _predictions(),
        simulation=_simulation(),
        assessment_day=90,
    )
    _assert_assessment_line_at_day(figure)

    axis = figure.axes[0]
    assert any(
        isinstance(collection, PolyCollection)
        for collection in axis.collections
    )
    assert any(
        line.get_linestyle() == "--"
        for line in axis.lines
        if line.get_label() != "Residue assessment"
    )
    assert any("simulation" in line.get_label() for line in axis.lines)


def test_simulation_heatmap_uses_green_yellow_red_pcolormesh() -> None:
    figure = plot_simulation_heatmap(
        _profile_simulation(),
        top_depth_mm=150,
        bottom_depth_mm=300,
        assessment_day=90,
    )
    _assert_assessment_line_at_day(figure)

    assert any(
        isinstance(collection, QuadMesh)
        for collection in figure.axes[0].collections
    )
    cmap = figure.axes[0].collections[0].cmap
    assert cmap(0.0)[:3] == (0.0, 0.40784313725490196, 0.21568627450980393)
    assert figure.axes[0].collections[0].get_clim() == (0.0, 15.0)


def test_simulation_heatmap_uses_realistic_display_scale_with_large_values() -> None:
    simulation = _profile_simulation().copy()
    simulation.loc[simulation.index[0], "concentration_ug_kg"] = 600.0

    figure = plot_simulation_heatmap(
        simulation,
        top_depth_mm=150,
        bottom_depth_mm=300,
    )

    assert figure.axes[0].collections[0].get_clim() == (0.0, 15.0)


def test_simulation_heatmap_handles_nullable_profile_concentrations() -> None:
    simulation = pd.DataFrame(
        {
            "time_days": [0, 30, 0, 30],
            "depth_mm": [0.0, 0.0, 150.0, 150.0],
            "concentration_ug_kg": pd.Series([10.0, pd.NA, 0.5, 1.0], dtype="Float64"),
        }
    )

    figure = plot_simulation_heatmap(
        simulation,
        top_depth_mm=150,
        bottom_depth_mm=300,
        assessment_day=30,
    )

    assert any(
        isinstance(collection, QuadMesh)
        for collection in figure.axes[0].collections
    )


def test_profile_curve_renders_one_assessment_day() -> None:
    figure = plot_profile_curve(
        _profile_simulation(),
        assessment_day=60,
        bottom_depth_mm=300,
    )

    assert figure.axes[0].lines
    assert figure.axes[0].get_ylim()[0] == 300


def test_soil_properties_plot_shows_soc_and_clay() -> None:
    figure = plot_soil_properties(_soil_properties())

    assert len(figure.axes) == 2
    assert {axis.get_title() for axis in figure.axes} == {"SOC", "Clay"}


def test_non_temporal_diagnostics_render_without_assessment_lines() -> None:
    density = plot_bulk_density(_bulk_density())

    assert not _assessment_lines(density)
