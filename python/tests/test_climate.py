#!/usr/bin/env python3
"""
Script: test_climate.py
Objective: Verify Python temperature-based PET against the R reference values.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Daily day-of-year and maximum/minimum temperatures.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_climate.py -q
Dependencies: numpy, pytest, cltf
"""

import numpy as np
import pytest

from cltf.climate import pet_from_temperature


def test_pet_matches_r_reference() -> None:
    result = pet_from_temperature(
        jday=[164, 165, 166, 167, 168],
        tmax_c=[18.4, 19.2, 20.1, 17.8, 16.5],
        tmin_c=[7.1, 6.8, 8.0, 5.6, 4.9],
        latitude_deg=-32.85,
    )
    np.testing.assert_allclose(
        result,
        [1.2, 1.3, 1.3, 1.2, 1.1],
        atol=1e-6,
    )


def test_pet_rejects_maximum_below_minimum() -> None:
    with pytest.raises(ValueError, match="below"):
        pet_from_temperature(164, 5, 6, -32.85)
