"""Two-layer Concentration Leaching and Transport (CLT) model."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np


@dataclass
class CLTParameters:
    """Parameter set for the two-layer CLT model."""

    mu: float
    sigma: float
    effective_porosity: float = 0.2
    retardation_top: float = 6.0
    decay_top: float = 0.0015
    reference_depth: float = 100.0
    retardation_bottom: float = 6.0
    decay_bottom: float = 0.03
    top_thickness_mm: float = 100.0
    bottom_depth_mm: float = 300.0
    dz: float = 0.01  # spatial discretisation (mm)
    min_value: float = 0.0  # fallback concentration when pdf is undefined


class TwoLayerCLT:
    """
    Translated from `CLT_1_integrated` in the R script.
    Provides top (0–top_thickness) and sub-layer (top_thickness–bottom_depth) averages.
    """

    def __init__(self, params: CLTParameters):
        self.params = params

    def _pdf(self, z: np.ndarray, cumulative_infiltration: float, time_days: float) -> np.ndarray:
        p = self.params
        # Linear increase in retardation with depth through lower layer
        wz = p.retardation_top + p.retardation_bottom * (np.maximum(z - p.top_thickness_mm, 0) / p.top_thickness_mm)
        top_mask = z <= p.top_thickness_mm

        with np.errstate(divide="ignore", invalid="ignore"):
            top_part = (
                1
                / (z * p.sigma * math.sqrt(2 * math.pi))
                * np.exp(-np.power(np.log((cumulative_infiltration * p.reference_depth) / (z * p.effective_porosity * p.retardation_top)) - p.mu, 2) / (2 * p.sigma**2) - p.decay_top * time_days)
            )
            bottom_part = np.exp(-p.decay_top * time_days) / (z * p.sigma * math.sqrt(2 * math.pi)) * np.exp(
                -np.power(np.log((cumulative_infiltration * p.reference_depth) / (z * p.effective_porosity * wz)) - p.mu, 2)
                / (2 * p.sigma**2)
                - p.decay_bottom * time_days
            )
        return np.where(top_mask, top_part, bottom_part)

    def integrated_concentration(
        self, cumulative_infiltration: float, time_days: float
    ) -> Tuple[float, float]:
        """
        Depth-averaged concentrations for the top and sub-layer.
        """
        p = self.params
        if cumulative_infiltration <= 0:
            # No infiltration yet: only decay in the top layer; bottom layer set to minimum value.
            return math.exp(-p.decay_top * time_days), p.min_value

        z = np.arange(1e-5, p.bottom_depth_mm + p.dz, p.dz)
        pdf = self._pdf(z, cumulative_infiltration, time_days)
        top_mask = z <= p.top_thickness_mm
        bottom_mask = (z > p.top_thickness_mm) & (z <= p.bottom_depth_mm)
        top_avg = pdf[top_mask].sum() * p.dz
        bottom_avg = pdf[bottom_mask].sum() * p.dz

        # Guard against non-finite or tiny values
        if not np.isfinite(top_avg):
            top_avg = p.min_value
        if not np.isfinite(bottom_avg):
            bottom_avg = p.min_value
        return top_avg, bottom_avg


def run_series(
    times_days: Iterable[float],
    cumulative_infiltration: Iterable[float],
    params: CLTParameters,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Run CLT forward for a time series.
    Returns top and bottom concentration arrays aligned with inputs.
    """
    times_arr = np.asarray(list(times_days), dtype=float)
    infil_arr = np.asarray(list(cumulative_infiltration), dtype=float)
    if len(times_arr) != len(infil_arr):
        raise ValueError("times_days and cumulative_infiltration must share length.")

    model = TwoLayerCLT(params)
    top_vals = np.zeros_like(times_arr, dtype=float)
    bottom_vals = np.zeros_like(times_arr, dtype=float)
    for i, (t, inf) in enumerate(zip(times_arr, infil_arr)):
        top_vals[i], bottom_vals[i] = model.integrated_concentration(inf, t)
    top_vals[~np.isfinite(top_vals)] = params.min_value
    bottom_vals[~np.isfinite(bottom_vals)] = params.min_value
    return top_vals, bottom_vals
