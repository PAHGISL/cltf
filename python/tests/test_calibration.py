#!/usr/bin/env python3
"""
Script: test_calibration.py
Objective: Verify replicate-level log-space CLTF calibration and profiles.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Deterministic synthetic forcing and concentration observations.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_calibration.py -q
Dependencies: numpy, pandas, pytest, cltf
"""

import numpy as np
import pandas as pd

from cltf.calibration import (
    cltf_objective,
    fit_cltf_profile,
    fit_cltf,
    profile_cltf_parameter,
)
from cltf.simulation import simulate_cltf, simulate_cltf_intervals
from cltf.transport import CLTFLayer


def _synthetic_case() -> tuple[pd.DataFrame, pd.DataFrame]:
    truth = {
        "mu": 1.0,
        "sigma": 0.5,
        "R_top": 2.0,
        "R_bottom": 3.0,
        "k": 0.005,
    }
    forcing = pd.DataFrame(
        {
            "time_days": np.linspace(5, 120, 12),
            "cumulative_infiltration_mm": np.linspace(80, 1400, 12),
        }
    )
    simulation = simulate_cltf(
        time_days=forcing["time_days"],
        cumulative_infiltration_mm=forcing["cumulative_infiltration_mm"],
        top_layer=CLTFLayer(
            truth["mu"],
            truth["sigma"],
            truth["R_top"],
            100,
        ),
        bottom_layer=CLTFLayer(
            truth["mu"],
            truth["sigma"],
            truth["R_bottom"],
            200,
        ),
        decay_rate_day=truth["k"],
        application_rate_g_ha=30,
        top_bulk_density_g_cm3=1.35,
        bottom_bulk_density_g_cm3=1.42,
        method="trapezoid",
        n_steps=501,
    )
    observations = pd.concat(
        [
            pd.DataFrame(
                {
                    "days_since_application": forcing["time_days"],
                    "depth_top_mm": 0.0,
                    "depth_bottom_mm": 100.0,
                    "concentration": simulation[
                        "concentration_top_ug_kg"
                    ],
                }
            ),
            pd.DataFrame(
                {
                    "days_since_application": forcing["time_days"],
                    "depth_top_mm": 100.0,
                    "depth_bottom_mm": 300.0,
                    "concentration": simulation[
                        "concentration_bottom_ug_kg"
                    ],
                }
            ),
        ],
        ignore_index=True,
    )
    rng = np.random.default_rng(42)
    observations["analysis_concentration_ug_kg"] = (
        observations.pop("concentration")
        * np.exp(rng.normal(0.0, 0.03, len(observations)))
    )
    return forcing, observations


def test_multistart_calibration_improves_objective() -> None:
    forcing, observations = _synthetic_case()
    initial = {
        "mu": 0.45,
        "sigma": 0.9,
        "R_top": 4.5,
        "R_bottom": 1.2,
        "k": 0.02,
    }
    lower = {
        "mu": 0.2,
        "sigma": 0.15,
        "R_top": 0.5,
        "R_bottom": 0.5,
        "k": 0.0,
    }
    upper = {
        "mu": 3.0,
        "sigma": 1.5,
        "R_top": 8.0,
        "R_bottom": 8.0,
        "k": 0.05,
    }
    context = {
        "observations": observations,
        "forcing": forcing,
        "application_rate_g_ha": 30,
        "top_bulk_density_g_cm3": 1.35,
        "bottom_bulk_density_g_cm3": 1.42,
        "method": "trapezoid",
        "n_steps": 501,
    }
    initial_objective = cltf_objective(initial, **context)
    fit = fit_cltf(
        **context,
        lower=lower,
        upper=upper,
        initial=initial,
        n_starts=3,
        seed=123,
        control={"maxit": 60},
    )

    assert np.isfinite(fit.objective)
    assert fit.objective < initial_objective
    assert set(fit.bound_hit) == {"mu", "sigma", "R_top", "R_bottom", "k"}
    assert len(fit.predictions) == len(observations)
    np.testing.assert_allclose(
        [
            fit.transport_scales["top"],
            fit.transport_scales["bottom"],
        ],
        [
            fit.parameters["mu"] * fit.parameters["R_top"],
            fit.parameters["mu"] * fit.parameters["R_bottom"],
        ],
    )
    assert "products" in fit.identifiability_note


def test_calibration_is_deterministic_and_profiles_fixed_parameter() -> None:
    forcing, observations = _synthetic_case()
    arguments = {
        "observations": observations,
        "forcing": forcing,
        "application_rate_g_ha": 30,
        "top_bulk_density_g_cm3": 1.35,
        "bottom_bulk_density_g_cm3": 1.42,
        "n_starts": 2,
        "seed": 99,
        "method": "trapezoid",
        "n_steps": 301,
        "control": {"maxit": 20},
    }
    first = fit_cltf(**arguments)
    second = fit_cltf(**arguments)
    assert second.parameters == first.parameters
    assert second.objective == first.objective
    assert second.start_index == first.start_index

    grid = np.asarray([first.parameters["k"] * 0.8, first.parameters["k"] * 1.2])
    profile = profile_cltf_parameter(
        first,
        parameter="k",
        grid=grid,
        control={"maxit": 10},
    )
    np.testing.assert_allclose(profile["parameter_value"], grid)
    assert np.all(np.isfinite(profile["objective"]))


def test_profile_calibration_uses_arbitrary_observation_intervals() -> None:
    truth = {"mu": 1.0, "sigma": 0.45, "R": 2.0, "k": 0.004}
    forcing = pd.DataFrame(
        {
            "time_days": np.array([0.0, 30.0, 60.0, 90.0]),
            "cumulative_infiltration_mm": np.array([0.0, 120.0, 300.0, 520.0]),
        }
    )
    intervals = pd.DataFrame(
        {
            "depth_top_mm": [0.0, 50.0, 150.0],
            "depth_bottom_mm": [50.0, 150.0, 300.0],
            "bulk_density_g_cm3": [1.3, 1.35, 1.4],
        }
    )
    simulation = simulate_cltf_intervals(
        forcing["time_days"],
        forcing["cumulative_infiltration_mm"],
        intervals[["depth_top_mm", "depth_bottom_mm"]],
        truth["mu"],
        truth["sigma"],
        truth["R"],
        truth["k"],
        application_rate_g_ha=30.0,
        bulk_density_g_cm3=intervals["bulk_density_g_cm3"],
    )
    observations = simulation.loc[
        simulation["time_days"].isin([30.0, 60.0, 90.0]),
        [
            "time_days",
            "depth_top_mm",
            "depth_bottom_mm",
            "concentration_ug_kg",
        ],
    ].rename(
        columns={
            "time_days": "days_since_application",
            "concentration_ug_kg": "analysis_concentration_ug_kg",
        }
    )
    observations["analysis_concentration_ug_kg"] *= np.exp(
        np.random.default_rng(7).normal(0.0, 0.02, len(observations))
    )

    fit = fit_cltf_profile(
        observations=observations,
        forcing=forcing,
        application_rate_g_ha=30.0,
        bulk_density=intervals,
        lower={"mu": 0.2, "sigma": 0.2, "R": 0.5, "k": 0.0},
        upper={"mu": 3.0, "sigma": 1.2, "R": 6.0, "k": 0.02},
        initial={"mu": 0.5, "sigma": 0.8, "R": 4.0, "k": 0.01},
        n_starts=2,
        seed=77,
        control={"maxit": 60},
    )

    assert fit.objective < 0.15
    assert set(fit.parameters) == {"mu", "sigma", "R", "k"}
    assert set(fit.bound_hit) == {"mu", "sigma", "R", "k"}
    assert len(fit.predictions) == len(observations)
    assert "mu * R" in fit.identifiability_note
