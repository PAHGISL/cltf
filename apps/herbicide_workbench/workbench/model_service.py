#!/usr/bin/env python3
"""
Script: model_service.py
Objective: Orchestrate direct Python CLTF fitting and simulation for the app.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: PreparedInputs, optional parameter settings, and optional assessment dates.
Outputs: RunResult objects with fitted parameters, predictions, diagnostics, and metadata.
Usage: Import fit_case and default_parameters from workbench.model_service.
Dependencies: dataclasses, numpy, pandas, cltf, workbench
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd

from workbench.assessment import default_assessment_date, summarize_assessment
from workbench.config import ensure_cltf_path
from workbench.contracts import PreparedInputs, RunResult

ensure_cltf_path()
from cltf import (  # noqa: E402
    fit_cltf_profile,
    infer_application_rate_g_ha,
    profile_cltf_profile_parameter,
    simulate_cltf_intervals,
    simulate_cltf_profile,
)


PARAMETER_NAMES = ("mu", "sigma", "R", "k")


@dataclass(frozen=True)
class ModelSettings:
    lower: dict[str, float]
    upper: dict[str, float]
    initial: dict[str, float]
    starts: pd.DataFrame | None = None
    n_starts: int = 5
    seed: int = 42
    effective_porosity: float = 0.2
    method: Literal["adaptive", "trapezoid"] = "trapezoid"
    n_steps: int = 1001
    rel_tol: float = 1e-8
    penalty: float = 1e6
    control: dict[str, Any] = field(default_factory=lambda: {"maxit": 80})
    profile_points: int = 3
    profile_control: dict[str, Any] = field(default_factory=lambda: {"maxit": 20})


def reference_starts() -> pd.DataFrame:
    """Return deterministic multistart values used by shared CLTF examples."""

    return pd.DataFrame(
        [
            [1.0, 0.6, 2.0, 0.005],
            [3.0, 1.1, 8.0, 0.02],
            [0.6, 0.4, 12.0, 0.004],
            [5.0, 1.6, 3.5, 0.03],
            [1.8, 0.9, 18.0, 0.01],
        ],
        columns=PARAMETER_NAMES,
    )


def default_parameters(**overrides: Any) -> ModelSettings:
    """Return app defaults matching the shared Python/R reference bounds."""

    settings = ModelSettings(
        lower={
            "mu": 0.05,
            "sigma": 0.10,
            "R": 0.10,
            "k": 0.0,
        },
        upper={
            "mu": 8.0,
            "sigma": 2.50,
            "R": 30.0,
            "k": 0.05,
        },
        initial={
            "mu": 1.0,
            "sigma": 0.6,
            "R": 2.0,
            "k": 0.005,
        },
        starts=reference_starts(),
    )
    if not overrides:
        return settings
    values = settings.__dict__.copy()
    values.update(overrides)
    return ModelSettings(**values)


def _layer_depths(prepared: PreparedInputs) -> tuple[float, float]:
    top_depth = float(prepared.site["top_depth_mm"])
    bottom_depth = float(prepared.site["bottom_depth_mm"])
    if top_depth <= 0 or bottom_depth <= top_depth:
        raise ValueError("Selected site must define two positive model layers")
    return top_depth, bottom_depth


def _calibration_observations(observations: pd.DataFrame) -> pd.DataFrame:
    if "used_for_calibration" in observations.columns:
        selected = observations.loc[observations["used_for_calibration"]].copy()
    else:
        selected = observations.copy()
    selected = selected.loc[
        pd.to_numeric(
            selected["analysis_concentration_ug_kg"],
            errors="coerce",
        ).gt(0)
    ].copy()
    if selected.empty:
        raise ValueError("No positive observations are available for CLTF calibration")
    return selected


def infer_application_rate_from_observations(
    observations: pd.DataFrame,
    top_depth_mm: float,
    top_bulk_density_g_cm3: float,
) -> float:
    """Infer applied mass from positive top-layer T0 observations."""

    is_t0 = (
        observations["is_t0"].astype(bool)
        if "is_t0" in observations.columns
        else observations["days_since_application"].eq(0)
    )
    selected = observations.loc[
        is_t0
        & observations["depth_top_mm"].eq(0)
        & observations["depth_bottom_mm"].eq(float(top_depth_mm))
        & observations["analysis_concentration_ug_kg"].gt(0)
    ]
    return infer_application_rate_g_ha(
        selected["analysis_concentration_ug_kg"],
        0.0,
        top_depth_mm,
        top_bulk_density_g_cm3,
    )


def _profile_grid(fit: Any, parameter: str, points: int) -> np.ndarray:
    span = fit.upper[parameter] - fit.lower[parameter]
    lower = max(fit.lower[parameter], fit.parameters[parameter] - 0.15 * span)
    upper = min(fit.upper[parameter], fit.parameters[parameter] + 0.15 * span)
    grid = np.linspace(lower, upper, max(2, int(points)))
    return np.unique(np.append(grid, fit.parameters[parameter]))


def build_objective_profiles(fit: Any, settings: ModelSettings) -> pd.DataFrame:
    """Build compact one-parameter objective profiles for diagnostics."""

    profiles = [
        profile_cltf_profile_parameter(
            fit,
            parameter=parameter,
            grid=_profile_grid(fit, parameter, settings.profile_points),
            control=settings.profile_control,
        )
        for parameter in PARAMETER_NAMES
    ]
    return pd.concat(profiles, ignore_index=True)


def _simulate_full_period(
    prepared: PreparedInputs,
    settings: ModelSettings,
    parameters: Mapping[str, float],
    application_rate_g_ha: float,
    top_depth_mm: float,
    bottom_depth_mm: float,
) -> pd.DataFrame:
    intervals = pd.DataFrame(
        {
            "depth_top_mm": [0.0, top_depth_mm],
            "depth_bottom_mm": [top_depth_mm, bottom_depth_mm],
        }
    )
    long = simulate_cltf_intervals(
        time_days=prepared.forcing["time_days"],
        cumulative_infiltration_mm=prepared.forcing[
            "cumulative_infiltration_mm"
        ],
        intervals_mm=intervals,
        mu=parameters["mu"],
        sigma=parameters["sigma"],
        retardation=parameters["R"],
        decay_rate_day=parameters["k"],
        application_rate_g_ha=application_rate_g_ha,
        bulk_density_g_cm3=[
            prepared.top_bulk_density_g_cm3,
            prepared.bottom_bulk_density_g_cm3,
        ],
        effective_porosity=settings.effective_porosity,
    )
    top_rows = long.loc[
        long["depth_top_mm"].eq(0.0)
        & long["depth_bottom_mm"].eq(top_depth_mm)
    ].set_index("time_days")
    bottom_rows = long.loc[
        long["depth_top_mm"].eq(top_depth_mm)
        & long["depth_bottom_mm"].eq(bottom_depth_mm)
    ].set_index("time_days")
    result = prepared.forcing.loc[
        :,
        ["date", "time_days", "cumulative_infiltration_mm"],
    ].copy()
    result["mass_top"] = top_rows.loc[
        result["time_days"],
        "mass_fraction",
    ].to_numpy()
    result["mass_bottom"] = bottom_rows.loc[
        result["time_days"],
        "mass_fraction",
    ].to_numpy()
    result["mass_below"] = top_rows.loc[
        result["time_days"],
        "mass_below_profile",
    ].to_numpy()
    result["mass_degraded"] = top_rows.loc[
        result["time_days"],
        "mass_degraded",
    ].to_numpy()
    result["concentration_top_ug_kg"] = top_rows.loc[
        result["time_days"],
        "concentration_ug_kg",
    ].to_numpy()
    result["concentration_bottom_ug_kg"] = bottom_rows.loc[
        result["time_days"],
        "concentration_ug_kg",
    ].to_numpy()
    return result


def _simulate_profile_period(
    prepared: PreparedInputs,
    settings: ModelSettings,
    parameters: Mapping[str, float],
    application_rate_g_ha: float,
    top_depth_mm: float,
    bottom_depth_mm: float,
) -> pd.DataFrame:
    depths = np.linspace(0.0, bottom_depth_mm, 61)
    density = np.where(
        depths <= top_depth_mm,
        prepared.top_bulk_density_g_cm3,
        prepared.bottom_bulk_density_g_cm3,
    )
    profile = simulate_cltf_profile(
        time_days=prepared.forcing["time_days"],
        cumulative_infiltration_mm=prepared.forcing[
            "cumulative_infiltration_mm"
        ],
        depths_mm=depths,
        mu=parameters["mu"],
        sigma=parameters["sigma"],
        retardation=parameters["R"],
        decay_rate_day=parameters["k"],
        application_rate_g_ha=application_rate_g_ha,
        bulk_density_g_cm3=density,
        effective_porosity=settings.effective_porosity,
    )
    dates = prepared.forcing.set_index("time_days")["date"]
    return pd.concat(
        [
            profile["time_days"].map(dates).rename("date"),
            profile,
        ],
        axis=1,
    )


def fit_case(
    prepared: PreparedInputs,
    settings: ModelSettings | None = None,
    assessment_date: object | None = None,
    application_rate_g_ha: float | None = None,
) -> RunResult:
    """Fit a prepared CLTF case and simulate the full observed-forcing period."""

    resolved = settings or default_parameters()
    top_depth, bottom_depth = _layer_depths(prepared)
    application_rate = (
        float(application_rate_g_ha)
        if application_rate_g_ha is not None
        else float(prepared.application_rate_g_ha)
    )
    calibration_observations = _calibration_observations(prepared.observations)
    fit = fit_cltf_profile(
        observations=calibration_observations,
        forcing=prepared.forcing,
        application_rate_g_ha=application_rate,
        bulk_density=prepared.bulk_density,
        lower=resolved.lower,
        upper=resolved.upper,
        initial=resolved.initial,
        starts=resolved.starts,
        n_starts=resolved.n_starts,
        seed=resolved.seed,
        effective_porosity=resolved.effective_porosity,
        penalty=resolved.penalty,
        control=resolved.control,
    )
    predictions = _simulate_full_period(
        prepared,
        resolved,
        fit.parameters,
        application_rate,
        top_depth,
        bottom_depth,
    )
    profile_simulation = _simulate_profile_period(
        prepared,
        resolved,
        fit.parameters,
        application_rate,
        top_depth,
        bottom_depth,
    )
    resolved_assessment_date = (
        pd.Timestamp(assessment_date).normalize()
        if assessment_date is not None
        else default_assessment_date(
            prepared.application_date,
            predictions["date"],
        )
    )
    assessment = summarize_assessment(predictions, resolved_assessment_date)
    objective_profiles = build_objective_profiles(fit, resolved)
    metadata = {
        "application_rate_g_ha": application_rate,
        "application_rate_source": (
            "advanced_override"
            if application_rate_g_ha is not None
            else "prepared_inputs"
        ),
        "effective_porosity": resolved.effective_porosity,
        "top_thickness_mm": top_depth,
        "bottom_thickness_mm": bottom_depth - top_depth,
        "convolution_method": "continuous_profile",
        "convolution_steps": None,
        "objective": fit.objective,
        "convergence": fit.convergence,
        "message": fit.message,
        "transport_scales": fit.transport_scales,
        "identifiability_note": fit.identifiability_note,
        "objective_profiles": objective_profiles,
        "profile_simulation": profile_simulation,
    }
    return RunResult(
        parameters=fit.parameters,
        predictions=predictions,
        fit=fit,
        assessment=assessment,
        warnings=[],
        metadata=metadata,
    )
