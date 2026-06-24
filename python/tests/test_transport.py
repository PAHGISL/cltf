#!/usr/bin/env python3
"""
Script: test_transport.py
Objective: Verify Python single- and two-layer CLTF transport calculations.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Fixed layer parameters and cumulative infiltration values.
Outputs: Pytest assertions for distributions and mass conservation.
Usage: python -m pytest python/tests/test_transport.py -q
Dependencies: numpy, scipy, pytest, cltf
"""

import numpy as np
import pytest
from scipy.stats import lognorm

from cltf.transport import (
    CLTFLayer,
    cltf_cdf,
    cltf_layer_probabilities,
    cltf_pdf,
    cltf_two_layer_cdf,
)


def test_single_layer_matches_scipy_lognormal() -> None:
    layer = CLTFLayer(mu=1.0, sigma=0.5, retardation=2.0, thickness_mm=100.0)
    y = np.array([0.0, 50.0, 100.0, 200.0, 500.0])
    scale = layer.mu * layer.retardation * layer.thickness_mm

    np.testing.assert_allclose(
        cltf_pdf(y, layer),
        lognorm.pdf(y, s=layer.sigma, scale=scale),
    )
    np.testing.assert_allclose(
        cltf_cdf(y, layer),
        lognorm.cdf(y, s=layer.sigma, scale=scale),
    )


def test_two_layer_probabilities_conserve_mass() -> None:
    top = CLTFLayer(1.0, 0.5, 2.0, 100.0)
    bottom = CLTFLayer(1.2, 0.6, 3.0, 200.0)
    result = cltf_layer_probabilities(
        np.array([0.0, 25.0, 100.0, 500.0, 5000.0]),
        top,
        bottom,
    )

    assert np.all(result >= 0)
    np.testing.assert_allclose(result.sum(axis=1), 1.0, atol=1e-10)
    np.testing.assert_allclose(result[0], [1.0, 0.0, 0.0])


def test_adaptive_and_trapezoid_convolution_agree() -> None:
    top = CLTFLayer(1.0, 0.5, 2.0, 100.0)
    bottom = CLTFLayer(1.2, 0.6, 3.0, 200.0)
    y = np.array([25.0, 100.0, 250.0, 500.0, 1000.0])

    adaptive = cltf_two_layer_cdf(y, top, bottom, method="adaptive")
    trapezoid = cltf_two_layer_cdf(
        y,
        top,
        bottom,
        method="trapezoid",
        n_steps=20001,
    )
    np.testing.assert_allclose(trapezoid, adaptive, atol=2e-4)


def test_transport_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="positive"):
        CLTFLayer(1.0, 0.0, 2.0, 100.0)
    layer = CLTFLayer(1.0, 0.5, 2.0, 100.0)
    with pytest.raises(ValueError, match="non-negative"):
        cltf_cdf([-1.0], layer)
    with pytest.raises(ValueError, match="odd"):
        cltf_two_layer_cdf([10.0], layer, layer, n_steps=100)
