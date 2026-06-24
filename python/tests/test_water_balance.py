#!/usr/bin/env python3
"""
Script: test_water_balance.py
Objective: Verify Python daily infiltration and generalized cumulative inverse.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Fixed rainfall, irrigation, ET, time, and cumulative infiltration.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_water_balance.py -q
Dependencies: numpy, pytest, cltf
"""

import numpy as np
import pytest

from cltf.water_balance import (
    cumulative_infiltration,
    daily_infiltration,
    first_passage_time,
)


def test_water_balance_matches_r_reference() -> None:
    np.testing.assert_allclose(
        daily_infiltration([0, 10, 2], [3, 3, 3], [5, 0, 0]),
        [2, 7, 0],
    )
    np.testing.assert_allclose(
        cumulative_infiltration([0, 10, 2], [3, 3, 3], [5, 0, 0]),
        [2, 9, 9],
    )


def test_first_passage_selects_start_of_plateau() -> None:
    np.testing.assert_allclose(
        first_passage_time(
            [0, 5, 5, 5, 9],
            [0, 1, 2, 3, 4],
            [0, 5, 6, 9, 10],
        ),
        [0, 1, 4, 4, np.nan],
        equal_nan=True,
    )


def test_water_balance_rejects_incompatible_lengths() -> None:
    with pytest.raises(ValueError, match="equal lengths"):
        daily_infiltration([1, 2], [1], [0, 0])
