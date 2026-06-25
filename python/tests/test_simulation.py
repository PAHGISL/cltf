#!/usr/bin/env python3
"""
Script: test_simulation.py
Objective: Verify Python end-to-end CLTF simulation and limiting cases.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Fixed forcing, model layers, degradation, mass, and soil properties.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_simulation.py -q
Dependencies: numpy, pytest, cltf
"""

import numpy as np
import pytest

from cltf.simulation import simulate_cltf, simulate_cltf_intervals, simulate_cltf_profile
from cltf.transport import CLTFLayer


def test_simulation_starts_in_top_layer() -> None:
    result = simulate_cltf(
        time_days=[0, 10],
        cumulative_infiltration_mm=[0, 0],
        top_layer=CLTFLayer(1.0, 0.5, 2.0, 100.0),
        bottom_layer=CLTFLayer(1.2, 0.6, 3.0, 200.0),
        decay_rate_day=0.01,
        application_rate_g_ha=21.32,
        top_bulk_density_g_cm3=1.3,
        bottom_bulk_density_g_cm3=1.4,
    )
    assert result.loc[0, "mass_top"] == 1
    assert result.loc[0, "concentration_top_ug_kg"] == 16.4
    np.testing.assert_allclose(
        result[
            ["mass_top", "mass_bottom", "mass_below", "mass_degraded"]
        ].sum(axis=1),
        1.0,
    )


def test_simulation_rejects_decreasing_forcing() -> None:
    with pytest.raises(ValueError, match="non-decreasing"):
        simulate_cltf(
            time_days=[0, 2, 1],
            cumulative_infiltration_mm=[0, 5, 10],
            top_layer=CLTFLayer(1.0, 0.5, 2.0, 100.0),
            bottom_layer=CLTFLayer(1.2, 0.6, 3.0, 200.0),
            decay_rate_day=0.01,
            application_rate_g_ha=20,
            top_bulk_density_g_cm3=1.3,
            bottom_bulk_density_g_cm3=1.4,
        )


def test_one_layer_interval_simulation_accepts_arbitrary_depths() -> None:
    intervals = np.array([[0.0, 50.0], [50.0, 150.0], [150.0, 300.0]])
    result = simulate_cltf_intervals(
        time_days=[0.0, 60.0],
        cumulative_infiltration_mm=[0.0, 400.0],
        intervals_mm=intervals,
        mu=1.0,
        sigma=0.5,
        retardation=2.0,
        decay_rate_day=0.001,
        application_rate_g_ha=30.0,
        bulk_density_g_cm3=[1.3, 1.35, 1.4],
    )

    assert len(result) == 6
    assert result["depth_top_mm"].tolist() == [0.0, 50.0, 150.0] * 2
    assert result["concentration_ug_kg"].ge(0).all()
    grouped = result.groupby("time_days")["mass_fraction"].sum()
    assert grouped.loc[0.0] == 1.0
    assert grouped.loc[60.0] < 1.0


def test_one_layer_profile_peak_moves_down_with_infiltration() -> None:
    depths = np.linspace(0.0, 300.0, 121)
    result = simulate_cltf_profile(
        time_days=[30.0, 60.0, 90.0],
        cumulative_infiltration_mm=[120.0, 240.0, 360.0],
        depths_mm=depths,
        mu=1.0,
        sigma=0.5,
        retardation=2.0,
        decay_rate_day=0.001,
        application_rate_g_ha=30.0,
        bulk_density_g_cm3=1.35,
    )

    peak_depths = (
        result.loc[result.groupby("time_days")["concentration_ug_kg"].idxmax()]
        .sort_values("time_days")["depth_mm"]
        .to_numpy()
    )
    surface = result.loc[result["depth_mm"].eq(0.0), "concentration_ug_kg"]

    assert surface.eq(0.0).all()
    assert np.all(np.diff(peak_depths) > 0)
