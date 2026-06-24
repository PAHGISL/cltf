#!/usr/bin/env python3
"""
Script: test_plotting.py
Objective: Verify all Python CLTF diagnostic plots render to non-empty PNGs.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Small deterministic forcing, prediction, simulation, profile, and soil tables.
Outputs: Non-empty temporary PNG files and pytest assertions.
Usage: MPLBACKEND=Agg python -m pytest python/tests/test_plotting.py -q
Dependencies: matplotlib, numpy, pandas, pytest, cltf
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from cltf.plotting import (
    plot_bulk_density,
    plot_climate_forcing,
    plot_mass_balance,
    plot_mass_fractions,
    plot_objective_profile,
    plot_observed_fitted,
    plot_residuals,
)


def test_plotting_primary_font_is_arial() -> None:
    assert matplotlib.rcParams["font.family"][0] == "Arial"


@pytest.fixture
def plot_data() -> dict[str, pd.DataFrame]:
    time = np.arange(6)
    forcing = pd.DataFrame(
        {
            "date": pd.date_range("2024-06-12", periods=6),
            "time_days": time,
            "rain_mm": [0, 5, 0, 12, 1, 0],
            "pet_mm": [1.2, 1.3, 1.3, 1.1, 1.0, 1.2],
            "daily_infiltration_mm": [0, 3.7, 0, 10.9, 0, 0],
            "cumulative_infiltration_mm": [0, 3.7, 3.7, 14.6, 14.6, 14.6],
        }
    )
    simulation = pd.DataFrame(
        {
            "time_days": time,
            "cumulative_infiltration_mm": forcing[
                "cumulative_infiltration_mm"
            ],
            "mass_top": np.linspace(1, 0.5, 6),
            "mass_bottom": np.linspace(0, 0.25, 6),
            "mass_below": np.linspace(0, 0.1, 6),
            "mass_degraded": np.linspace(0, 0.15, 6),
            "concentration_top_ug_kg": np.linspace(16, 8, 6),
            "concentration_bottom_ug_kg": np.linspace(0.2, 2, 6),
        }
    )
    prediction_frames = []
    for depth_top, depth_bottom, observed, fitted in (
        (0, 100, np.linspace(16, 8, 6), np.linspace(15.5, 8.2, 6)),
        (100, 300, np.linspace(0.3, 2, 6), np.linspace(0.25, 1.9, 6)),
    ):
        prediction_frames.append(
            pd.DataFrame(
                {
                    "days_since_application": np.repeat(time, 2),
                    "depth_top_mm": depth_top,
                    "depth_bottom_mm": depth_bottom,
                    "replicate_id": np.tile([1, 2], 6),
                    "analysis_concentration_ug_kg": (
                        np.repeat(observed, 2) * np.tile([0.95, 1.05], 6)
                    ),
                    "predicted_concentration_ug_kg": np.repeat(fitted, 2),
                }
            )
        )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions["log_residual"] = np.log(
        predictions["analysis_concentration_ug_kg"]
    ) - np.log(predictions["predicted_concentration_ug_kg"])
    profile = pd.DataFrame(
        {
            "parameter": "k",
            "parameter_value": np.linspace(0.001, 0.01, 8),
            "objective": [0.8, 0.5, 0.3, 0.2, 0.21, 0.3, 0.5, 0.75],
        }
    )
    bulk_density = pd.DataFrame(
        {
            "depth_top_mm": [0, 50, 150],
            "depth_bottom_mm": [50, 150, 300],
            "estimate_g_cm3": [1.32, 1.38, 1.43],
            "lower_g_cm3": [1.18, 1.22, 1.28],
            "upper_g_cm3": [1.46, 1.54, 1.58],
            "source": "SLGA fixture",
        }
    )
    return {
        "forcing": forcing,
        "simulation": simulation,
        "predictions": predictions,
        "profile": profile,
        "bulk_density": bulk_density,
    }


@pytest.mark.parametrize(
    ("function", "data_key"),
    [
        (plot_climate_forcing, "forcing"),
        (plot_observed_fitted, "predictions"),
        (plot_residuals, "predictions"),
        (plot_mass_fractions, "simulation"),
        (plot_mass_balance, "simulation"),
        (plot_objective_profile, "profile"),
        (plot_bulk_density, "bulk_density"),
    ],
)
def test_plot_renders_non_empty_png(
    function,
    data_key: str,
    plot_data: dict[str, pd.DataFrame],
    tmp_path: Path,
) -> None:
    figure = function(plot_data[data_key])
    output = tmp_path / f"{function.__name__}.png"
    figure.savefig(output, dpi=100)
    plt.close(figure)
    assert output.stat().st_size > 0
