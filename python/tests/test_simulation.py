#!/usr/bin/env python3
"""
Script: test_simulation.py
Objective: Verify Python end-to-end CLTF simulation and limiting cases.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Fixed forcing, model layers, degradation, mass, and soil properties.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_simulation.py -q
Dependencies: numpy, pytest, cltf
"""

import numpy as np
import pytest

from cltf.simulation import simulate_cltf
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
