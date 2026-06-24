#!/usr/bin/env python3
"""
Script: simulation.py
Objective: Run conservative two-layer CLTF simulations over forcing time series.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
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
