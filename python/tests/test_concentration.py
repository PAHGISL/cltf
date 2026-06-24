#!/usr/bin/env python3
"""
Script: test_concentration.py
Objective: Verify Python soil-mass, degradation, and concentration calculations.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Fixed masses, fractions, depths, densities, and elapsed times.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_concentration.py -q
Dependencies: numpy, pytest, cltf
"""

import numpy as np

from cltf.concentration import (
    apply_elapsed_degradation,
    resident_concentration_ug_kg,
    soil_mass_kg_ha,
)


def test_concentration_arithmetic() -> None:
    soil_mass = soil_mass_kg_ha(0, 100, 1.3)
    assert soil_mass == 1.3e6
    assert resident_concentration_ug_kg(21.32, 1.0, soil_mass, 0.2) == 16.4


def test_effective_porosity_is_a_normalized_scale() -> None:
    baseline = resident_concentration_ug_kg(20, 0.5, 1e6, 0.2)
    doubled_porosity = resident_concentration_ug_kg(20, 0.5, 1e6, 0.4)
    assert doubled_porosity == baseline / 2


def test_elapsed_degradation_completes_mass_balance() -> None:
    probabilities = np.array([[0.4, 0.3, 0.3]])
    result = apply_elapsed_degradation(probabilities, np.array([100.0]), 0.01)
    np.testing.assert_allclose(result.sum(axis=1), 1.0, atol=1e-12)
