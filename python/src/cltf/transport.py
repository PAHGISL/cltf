#!/usr/bin/env python3
"""
Script: transport.py
Objective: Implement validated single- and two-layer CLTF transport calculations.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Layer parameters and cumulative infiltration values.
Outputs: Transfer densities, cumulative probabilities, and layer mass fractions.
Usage: Import public functions from cltf or cltf.transport.
Dependencies: math, dataclasses, numpy, scipy
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike
from scipy.integrate import quad, trapezoid
from scipy.stats import lognorm, norm


@dataclass(frozen=True)
class CLTFLayer:
    """Validated parameters for one CLTF soil layer."""

    mu: float
    sigma: float
    retardation: float
    thickness_mm: float

    def __post_init__(self) -> None:
        values = (self.mu, self.sigma, self.retardation, self.thickness_mm)
        if not all(math.isfinite(value) and value > 0 for value in values):
            raise ValueError("CLTF layer parameters must be finite and positive")

    @property
    def scale_mm(self) -> float:
        """Lognormal scale in millimetres of cumulative infiltration."""

        return self.mu * self.retardation * self.thickness_mm

    @property
    def meanlog(self) -> float:
        """Lognormal mean on the logarithmic scale."""

        return math.log(self.scale_mm)


def _non_negative_array(values: ArrayLike, name: str) -> np.ndarray:
    result = np.atleast_1d(np.asarray(values, dtype=float))
    if not np.all(np.isfinite(result)) or np.any(result < 0):
        raise ValueError(f"{name} must contain finite non-negative values")
    return result


def cltf_pdf(y_mm: ArrayLike, layer: CLTFLayer) -> np.ndarray:
    """Evaluate a single-layer CLTF density."""

    y = _non_negative_array(y_mm, "y_mm")
    return lognorm.pdf(y, s=layer.sigma, scale=layer.scale_mm)


def cltf_cdf(y_mm: ArrayLike, layer: CLTFLayer) -> np.ndarray:
    """Evaluate a single-layer CLTF cumulative distribution."""

    y = _non_negative_array(y_mm, "y_mm")
    return lognorm.cdf(y, s=layer.sigma, scale=layer.scale_mm)


def _two_layer_cdf_scalar(
    y_mm: float,
    top_layer: CLTFLayer,
    bottom_layer: CLTFLayer,
    method: Literal["adaptive", "trapezoid"],
    n_steps: int,
    rel_tol: float,
) -> float:
    if y_mm == 0:
        return 0.0

    if method == "adaptive":

        def integrand(log_u: float) -> float:
            u = math.exp(log_u)
            remaining = max(y_mm - u, 0.0)
            return float(
                norm.pdf(
                    log_u,
                    loc=top_layer.meanlog,
                    scale=top_layer.sigma,
                )
                * cltf_cdf([remaining], bottom_layer)[0]
            )

        value, _ = quad(
            integrand,
            -np.inf,
            math.log(y_mm),
            epsrel=rel_tol,
            limit=1000,
        )
        return float(value)

    grid = np.linspace(0.0, y_mm, n_steps)
    integrand = cltf_pdf(grid, top_layer) * cltf_cdf(
        y_mm - grid,
        bottom_layer,
    )
    return float(trapezoid(integrand, grid))


def cltf_two_layer_cdf(
    y_mm: ArrayLike,
    top_layer: CLTFLayer,
    bottom_layer: CLTFLayer,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 5001,
    rel_tol: float = 1e-8,
) -> np.ndarray:
    """Evaluate the sequential two-layer CLTF cumulative distribution."""

    y = _non_negative_array(y_mm, "y_mm")
    if method not in {"adaptive", "trapezoid"}:
        raise ValueError("method must be 'adaptive' or 'trapezoid'")
    if not isinstance(n_steps, int) or n_steps < 3 or n_steps % 2 == 0:
        raise ValueError("n_steps must be one odd integer of at least 3")
    if not math.isfinite(rel_tol) or rel_tol <= 0:
        raise ValueError("rel_tol must be finite and positive")

    result = np.array(
        [
            _two_layer_cdf_scalar(
                value,
                top_layer,
                bottom_layer,
                method,
                n_steps,
                rel_tol,
            )
            for value in y
        ],
        dtype=float,
    )
    return np.clip(result, 0.0, 1.0)


def cltf_layer_probabilities(
    y_mm: ArrayLike,
    top_layer: CLTFLayer,
    bottom_layer: CLTFLayer,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 5001,
    rel_tol: float = 1e-8,
    tolerance: float = 1e-8,
) -> np.ndarray:
    """Calculate top, bottom, and below-profile resident mass fractions."""

    y = _non_negative_array(y_mm, "y_mm")
    g1 = cltf_cdf(y, top_layer)
    g12 = cltf_two_layer_cdf(
        y,
        top_layer,
        bottom_layer,
        method=method,
        n_steps=n_steps,
        rel_tol=rel_tol,
    )
    result = np.column_stack((1.0 - g1, g1 - g12, g12))
    row_sums = result.sum(axis=1)
    if (
        np.any(result < -tolerance)
        or np.any(result > 1.0 + tolerance)
        or np.any(np.abs(row_sums - 1.0) > tolerance)
    ):
        raise ValueError("Layer probabilities violate numerical mass balance")
    result[(result < 0) & (result >= -tolerance)] = 0.0
    return result / result.sum(axis=1, keepdims=True)
