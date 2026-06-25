#!/usr/bin/env python3
"""
Script: simulation.py
Objective: Run conservative two-layer CLTF simulations over forcing time series.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Time, cumulative infiltration, layers, degradation, mass, and soil properties.
Outputs: Time-indexed mass fractions and resident concentrations.
Usage: Import simulate_cltf from cltf or cltf.simulation.
Dependencies: numpy, pandas, cltf.concentration, cltf.transport
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from .concentration import (
    apply_elapsed_degradation,
    resident_concentration_ug_kg,
    soil_mass_kg_ha,
)
from .transport import CLTFLayer, cltf_layer_probabilities
from .transport import cltf_interval_probabilities


def _validated_forcing(
    time_days: ArrayLike,
    cumulative_infiltration_mm: ArrayLike,
) -> tuple[np.ndarray, np.ndarray]:
    time = np.atleast_1d(np.asarray(time_days, dtype=float))
    infiltration = np.atleast_1d(
        np.asarray(cumulative_infiltration_mm, dtype=float)
    )
    if len(time) == 0 or len(time) != len(infiltration):
        raise ValueError("Time and infiltration vectors must have equal non-zero lengths")
    if (
        not np.all(np.isfinite(time))
        or np.any(time < 0)
        or np.any(np.diff(time) < 0)
    ):
        raise ValueError(
            "time_days must be finite, non-negative, and non-decreasing"
        )
    if (
        not np.all(np.isfinite(infiltration))
        or np.any(infiltration < 0)
        or np.any(np.diff(infiltration) < 0)
    ):
        raise ValueError(
            "Cumulative infiltration must be finite, non-negative, and non-decreasing"
        )
    return time, infiltration


def _validated_intervals(intervals_mm: ArrayLike) -> np.ndarray:
    intervals = np.asarray(intervals_mm, dtype=float)
    if intervals.ndim != 2 or intervals.shape[1] != 2:
        raise ValueError("intervals_mm must be a two-column array")
    if (
        not np.all(np.isfinite(intervals))
        or np.any(intervals[:, 0] < 0)
        or np.any(intervals[:, 1] <= intervals[:, 0])
    ):
        raise ValueError("Depth intervals must be finite, non-negative, and positive")
    order = np.argsort(intervals[:, 0], kind="stable")
    return intervals[order, :]


def _validated_interval_density(
    bulk_density_g_cm3: ArrayLike,
    n_intervals: int,
) -> np.ndarray:
    density = np.asarray(bulk_density_g_cm3, dtype=float)
    if density.ndim == 0:
        density = np.full(n_intervals, float(density))
    density = np.atleast_1d(density)
    if (
        density.ndim != 1
        or len(density) != n_intervals
        or not np.all(np.isfinite(density))
        or np.any(density <= 0)
    ):
        raise ValueError(
            "bulk_density_g_cm3 must be one positive value per depth interval"
        )
    return density


def _validated_positive_scalar(value: float, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return result


def simulate_cltf_intervals(
    time_days: ArrayLike,
    cumulative_infiltration_mm: ArrayLike,
    intervals_mm: ArrayLike,
    mu: float,
    sigma: float,
    retardation: float,
    decay_rate_day: float,
    application_rate_g_ha: float,
    bulk_density_g_cm3: ArrayLike,
    effective_porosity: float = 0.2,
) -> pd.DataFrame:
    """Simulate continuous one-layer CLTF concentration for depth intervals."""

    time, infiltration = _validated_forcing(
        time_days,
        cumulative_infiltration_mm,
    )
    intervals = _validated_intervals(intervals_mm)
    density = _validated_interval_density(bulk_density_g_cm3, len(intervals))
    _validated_positive_scalar(mu, "mu")
    _validated_positive_scalar(sigma, "sigma")
    _validated_positive_scalar(retardation, "retardation")
    if not np.isfinite(decay_rate_day) or decay_rate_day < 0:
        raise ValueError("decay_rate_day must be finite and non-negative")

    probabilities = cltf_interval_probabilities(
        infiltration,
        intervals,
        mu=mu,
        sigma=sigma,
        retardation=retardation,
    )
    remaining = np.exp(-float(decay_rate_day) * time)
    interval_mass = probabilities[:, :-1] * remaining[:, np.newaxis]
    below = probabilities[:, -1] * remaining
    degraded = 1.0 - remaining
    soil_masses = np.array(
        [
            soil_mass_kg_ha(top, bottom, interval_density)
            for (top, bottom), interval_density in zip(intervals, density)
        ],
        dtype=float,
    )

    rows = []
    for time_index, (day, infiltrated) in enumerate(zip(time, infiltration)):
        for interval_index, (top, bottom) in enumerate(intervals):
            mass_fraction = interval_mass[time_index, interval_index]
            rows.append(
                {
                    "time_days": day,
                    "cumulative_infiltration_mm": infiltrated,
                    "depth_top_mm": top,
                    "depth_bottom_mm": bottom,
                    "mass_fraction": mass_fraction,
                    "mass_below_profile": below[time_index],
                    "mass_degraded": degraded[time_index],
                    "concentration_ug_kg": resident_concentration_ug_kg(
                        application_rate_g_ha,
                        mass_fraction,
                        soil_masses[interval_index],
                        effective_porosity,
                    ),
                }
            )
    return pd.DataFrame(rows)


def _depth_edges(depths_mm: np.ndarray) -> np.ndarray:
    if depths_mm.ndim != 1 or len(depths_mm) == 0:
        raise ValueError("depths_mm must contain at least one depth")
    if not np.all(np.isfinite(depths_mm)) or np.any(depths_mm < 0):
        raise ValueError("depths_mm must contain finite non-negative depths")
    if len(depths_mm) == 1:
        width = max(float(depths_mm[0]), 1.0)
        return np.array([max(0.0, depths_mm[0] - width / 2.0), depths_mm[0] + width / 2.0])
    if np.any(np.diff(depths_mm) <= 0):
        raise ValueError("depths_mm must be strictly increasing")
    midpoints = (depths_mm[:-1] + depths_mm[1:]) / 2.0
    first = max(0.0, depths_mm[0] - (depths_mm[1] - depths_mm[0]) / 2.0)
    last = depths_mm[-1] + (depths_mm[-1] - depths_mm[-2]) / 2.0
    return np.concatenate(([first], midpoints, [last]))


def _spatial_density_per_mm(
    cumulative_infiltration_mm: np.ndarray,
    depths_mm: np.ndarray,
    mu: float,
    sigma: float,
    retardation: float,
) -> np.ndarray:
    density = np.zeros(
        (len(cumulative_infiltration_mm), len(depths_mm)),
        dtype=float,
    )
    positive_time = cumulative_infiltration_mm > 0
    positive_depth = depths_mm > 0
    if not np.any(positive_time) or not np.any(positive_depth):
        return density

    y = cumulative_infiltration_mm[positive_time, np.newaxis]
    depth = depths_mm[positive_depth][np.newaxis, :]
    log_ratio = np.log(y / (mu * retardation * depth))
    density[np.ix_(positive_time, positive_depth)] = (
        np.exp(-(log_ratio**2) / (2.0 * sigma**2))
        / (depth * sigma * np.sqrt(2.0 * np.pi))
    )
    return density


def simulate_cltf_profile(
    time_days: ArrayLike,
    cumulative_infiltration_mm: ArrayLike,
    depths_mm: ArrayLike,
    mu: float,
    sigma: float,
    retardation: float,
    decay_rate_day: float,
    application_rate_g_ha: float,
    bulk_density_g_cm3: ArrayLike,
    effective_porosity: float = 0.2,
) -> pd.DataFrame:
    """Simulate a continuous CLTF profile on a depth grid."""

    time, infiltration = _validated_forcing(
        time_days,
        cumulative_infiltration_mm,
    )
    depths = np.asarray(depths_mm, dtype=float)
    if (
        depths.ndim != 1
        or len(depths) == 0
        or not np.all(np.isfinite(depths))
        or np.any(depths < 0)
        or np.any(np.diff(depths) <= 0)
    ):
        raise ValueError("depths_mm must be finite, non-negative, and increasing")
    density = np.asarray(bulk_density_g_cm3, dtype=float)
    if density.ndim == 0:
        depth_density = np.full(len(depths), float(density))
    else:
        density = np.atleast_1d(density)
        if len(density) != len(depths):
            raise ValueError("bulk_density_g_cm3 must be scalar or one value per depth")
        depth_density = density
    if not np.all(np.isfinite(depth_density)) or np.any(depth_density <= 0):
        raise ValueError("bulk_density_g_cm3 must contain positive finite values")
    _validated_positive_scalar(mu, "mu")
    _validated_positive_scalar(sigma, "sigma")
    _validated_positive_scalar(retardation, "retardation")
    if not np.isfinite(decay_rate_day) or decay_rate_day < 0:
        raise ValueError("decay_rate_day must be finite and non-negative")
    if (
        not np.isfinite(application_rate_g_ha)
        or application_rate_g_ha < 0
        or not np.isfinite(effective_porosity)
        or effective_porosity <= 0
    ):
        raise ValueError("Application rate and porosity inputs are invalid")

    mass_density = _spatial_density_per_mm(
        infiltration,
        depths,
        mu,
        sigma,
        retardation,
    )
    mass_density *= np.exp(-float(decay_rate_day) * time)[:, np.newaxis]
    soil_mass_per_mm = np.asarray(
        [soil_mass_kg_ha(0.0, 1.0, value) for value in depth_density],
        dtype=float,
    )
    concentration = (
        float(application_rate_g_ha)
        * 1e6
        * mass_density
        / soil_mass_per_mm[np.newaxis, :]
        * (0.2 / float(effective_porosity))
    )

    rows = []
    for time_index, (day, infiltrated) in enumerate(zip(time, infiltration)):
        for depth_index, depth in enumerate(depths):
            rows.append(
                {
                    "time_days": day,
                    "cumulative_infiltration_mm": infiltrated,
                    "depth_mm": depth,
                    "mass_density_per_mm": mass_density[time_index, depth_index],
                    "concentration_ug_kg": concentration[time_index, depth_index],
                }
            )
    return pd.DataFrame(rows)


def simulate_cltf(
    time_days: ArrayLike,
    cumulative_infiltration_mm: ArrayLike,
    top_layer: CLTFLayer,
    bottom_layer: CLTFLayer,
    decay_rate_day: float,
    application_rate_g_ha: float,
    top_bulk_density_g_cm3: float,
    bottom_bulk_density_g_cm3: float,
    effective_porosity: float = 0.2,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 5001,
    rel_tol: float = 1e-8,
) -> pd.DataFrame:
    """Simulate a conservative two-layer CLTF time series."""

    time, infiltration = _validated_forcing(time_days, cumulative_infiltration_mm)

    probabilities = cltf_layer_probabilities(
        infiltration,
        top_layer,
        bottom_layer,
        method=method,
        n_steps=n_steps,
        rel_tol=rel_tol,
    )
    balance = apply_elapsed_degradation(
        probabilities,
        time,
        decay_rate_day,
    )
    top_soil_mass = soil_mass_kg_ha(
        0.0,
        top_layer.thickness_mm,
        top_bulk_density_g_cm3,
    )
    bottom_soil_mass = soil_mass_kg_ha(
        top_layer.thickness_mm,
        top_layer.thickness_mm + bottom_layer.thickness_mm,
        bottom_bulk_density_g_cm3,
    )

    return pd.DataFrame(
        {
            "time_days": time,
            "cumulative_infiltration_mm": infiltration,
            "mass_top": balance[:, 0],
            "mass_bottom": balance[:, 1],
            "mass_below": balance[:, 2],
            "mass_degraded": balance[:, 3],
            "concentration_top_ug_kg": resident_concentration_ug_kg(
                application_rate_g_ha,
                balance[:, 0],
                top_soil_mass,
                effective_porosity,
            ),
            "concentration_bottom_ug_kg": resident_concentration_ug_kg(
                application_rate_g_ha,
                balance[:, 1],
                bottom_soil_mass,
                effective_porosity,
            ),
        }
    )
