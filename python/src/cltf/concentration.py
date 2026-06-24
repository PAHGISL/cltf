#!/usr/bin/env python3
"""
Script: concentration.py
Objective: Convert CLTF mass fractions into layer-average dry-soil concentrations.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Application mass, fractions, elapsed time, depths, density, and porosity.
Outputs: Soil masses, degraded fractions, and concentrations in micrograms per kilogram.
Usage: Import public functions from cltf or cltf.concentration.
Dependencies: math, numpy
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike


def soil_mass_kg_ha(
    depth_top_mm: float,
    depth_bottom_mm: float,
    bulk_density_g_cm3: float,
) -> float:
    """Calculate dry soil mass per hectare."""

    values = (depth_top_mm, depth_bottom_mm, bulk_density_g_cm3)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Depth and bulk density values must be finite")
    if depth_top_mm < 0 or depth_bottom_mm <= depth_top_mm:
        raise ValueError("depth_bottom_mm must be greater than depth_top_mm")
    if bulk_density_g_cm3 <= 0:
        raise ValueError("bulk_density_g_cm3 must be greater than zero")
    thickness_m = (depth_bottom_mm - depth_top_mm) / 1000.0
    density_kg_m3 = bulk_density_g_cm3 * 1000.0
    return 10000.0 * thickness_m * density_kg_m3


def apply_elapsed_degradation(
    layer_probabilities: ArrayLike,
    time_days: ArrayLike,
    decay_rate_day: float,
) -> np.ndarray:
    """Apply one first-order degradation rate over total elapsed time."""

    probabilities = np.asarray(layer_probabilities, dtype=float)
    time = np.atleast_1d(np.asarray(time_days, dtype=float))
    if (
        probabilities.ndim != 2
        or probabilities.shape[1] != 3
        or not np.all(np.isfinite(probabilities))
        or np.any(probabilities < 0)
        or np.any(np.abs(probabilities.sum(axis=1) - 1.0) > 1e-8)
    ):
        raise ValueError(
            "layer_probabilities must be a finite three-column probability matrix"
        )
    if (
        len(time) != len(probabilities)
        or not np.all(np.isfinite(time))
        or np.any(time < 0)
    ):
        raise ValueError("One finite non-negative elapsed time is required per row")
    if not math.isfinite(decay_rate_day) or decay_rate_day < 0:
        raise ValueError("decay_rate_day must be finite and non-negative")

    remaining = np.exp(-decay_rate_day * time)
    return np.column_stack(
        (
            probabilities * remaining[:, np.newaxis],
            1.0 - remaining,
        )
    )


def resident_concentration_ug_kg(
    application_rate_g_ha: float,
    remaining_fraction: ArrayLike,
    soil_mass_kg_ha: float,
    effective_porosity: float = 0.2,
) -> float | np.ndarray:
    """Convert applied mass and a remaining fraction to resident concentration."""

    fractions = np.asarray(remaining_fraction, dtype=float)
    scalar_input = fractions.ndim == 0
    if (
        not math.isfinite(application_rate_g_ha)
        or application_rate_g_ha < 0
        or not np.all(np.isfinite(fractions))
        or np.any(fractions < 0)
        or np.any(fractions > 1)
        or not math.isfinite(soil_mass_kg_ha)
        or soil_mass_kg_ha <= 0
        or not math.isfinite(effective_porosity)
        or effective_porosity <= 0
    ):
        raise ValueError("Mass, fraction, soil mass, and porosity inputs are invalid")

    result = (
        application_rate_g_ha
        * 1e6
        / soil_mass_kg_ha
        * fractions
        * (0.2 / effective_porosity)
    )
    return float(result) if scalar_input else result
