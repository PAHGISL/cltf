#!/usr/bin/env python3
"""
Script: water_balance.py
Objective: Convert daily water inputs and ET into infiltration and passage times.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Daily rainfall, irrigation, ET, time, and cumulative infiltration.
Outputs: Daily/cumulative infiltration and first-passage time arrays.
Usage: Import public functions from cltf or cltf.water_balance.
Dependencies: math, numpy
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike


def daily_infiltration(
    rain_mm: ArrayLike,
    et_mm: ArrayLike,
    irrigation_mm: ArrayLike | None = None,
    et_factor: float = 1.0,
) -> np.ndarray:
    """Calculate thresholded daily net infiltration in millimetres."""

    rain = np.atleast_1d(np.asarray(rain_mm, dtype=float))
    et = np.atleast_1d(np.asarray(et_mm, dtype=float))
    irrigation = (
        np.zeros_like(rain)
        if irrigation_mm is None
        else np.atleast_1d(np.asarray(irrigation_mm, dtype=float))
    )
    if len({len(rain), len(et), len(irrigation)}) != 1:
        raise ValueError("Water-balance vectors must have equal lengths")
    if (
        not np.all(np.isfinite(rain))
        or not np.all(np.isfinite(et))
        or not np.all(np.isfinite(irrigation))
        or np.any(rain < 0)
        or np.any(et < 0)
        or np.any(irrigation < 0)
        or not math.isfinite(et_factor)
        or et_factor < 0
    ):
        raise ValueError("Water-balance inputs must be finite and non-negative")

    return np.maximum(rain + irrigation - et_factor * et, 0.0)


def cumulative_infiltration(
    rain_mm: ArrayLike,
    et_mm: ArrayLike,
    irrigation_mm: ArrayLike | None = None,
    et_factor: float = 1.0,
) -> np.ndarray:
    """Calculate cumulative thresholded net infiltration in millimetres."""

    return np.cumsum(
        daily_infiltration(
            rain_mm,
            et_mm,
            irrigation_mm=irrigation_mm,
            et_factor=et_factor,
        )
    )


def first_passage_time(
    cumulative_infiltration_mm: ArrayLike,
    time: ArrayLike,
    target_infiltration_mm: ArrayLike,
) -> np.ndarray:
    """Return the first time at which each infiltration target is reached."""

    infiltration = np.atleast_1d(
        np.asarray(cumulative_infiltration_mm, dtype=float)
    )
    time_values = np.atleast_1d(np.asarray(time, dtype=float))
    targets = np.atleast_1d(
        np.asarray(target_infiltration_mm, dtype=float)
    )
    if len(infiltration) != len(time_values):
        raise ValueError(
            "Cumulative infiltration and time must have equal lengths"
        )
    if (
        not np.all(np.isfinite(infiltration))
        or np.any(infiltration < 0)
        or np.any(np.diff(infiltration) < 0)
    ):
        raise ValueError(
            "Cumulative infiltration must be finite and non-decreasing"
        )
    if (
        not np.all(np.isfinite(time_values))
        or np.any(np.diff(time_values) <= 0)
    ):
        raise ValueError("time must be finite and strictly increasing")
    if not np.all(np.isfinite(targets)) or np.any(targets < 0):
        raise ValueError("Targets must be finite and non-negative")

    indices = np.searchsorted(infiltration, targets, side="left")
    result = np.full(targets.shape, np.nan, dtype=float)
    reached = indices < len(infiltration)
    result[reached] = time_values[indices[reached]]
    return result
