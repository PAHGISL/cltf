#!/usr/bin/env python3
"""
Script: model_service.py
Objective: Orchestrate direct Python CLTF fitting and simulation for the app.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
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
    CLTFLayer,
    fit_cltf,
    infer_application_rate_g_ha,
    profile_cltf_parameter,
    simulate_cltf,
)


PARAMETER_NAMES = ("mu", "sigma", "R_top", "R_bottom", "k")


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
            [1.0, 0.6, 2.0, 3.0, 0.005],
            [
                7.32270804579603,
                1.64018924534321,
                13.1741465789964,
                28.046700189868,
                0.0489113214192912,
            ],
            [
                7.499749535718,
                1.34583027791232,
                14.1307892023353,
                7.73732184779365,
                0.00587436808273196,
            ],
            [
                2.32480930155143,
                1.86781195513904,
                9.20906134734396,
                13.9225553940516,
                0.0237498540780507,
            ],
            [
                6.65205862723524,
                0.423199833370745,
                14.4103338078829,
                28.20643423039,
                0.0280166373122483,
            ],
        ],
        columns=PARAMETER_NAMES,
    )


def default_parameters(**overrides: Any) -> ModelSettings:
    """Return app defaults matching the shared Python/R reference bounds."""

    settings = ModelSettings(
        lower={
            "mu": 0.05,
            "sigma": 0.10,
            "R_top": 0.10,
            "R_bottom": 0.10,
            "k": 0.0,
        },
        upper={
            "mu": 8.0,
            "sigma": 2.50,
            "R_top": 20.0,
            "R_bottom": 30.0,
            "k": 0.05,
        },
        initial={
            "mu": 1.0,
            "sigma": 0.6,
            "R_top": 2.0,
            "R_bottom": 3.0,
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
        profile_cltf_parameter(
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
    top_thickness_mm: float,
    bottom_thickness_mm: float,
) -> pd.DataFrame:
    simulation = simulate_cltf(
        time_days=prepared.forcing["time_days"],
        cumulative_infiltration_mm=prepared.forcing[
            "cumulative_infiltration_mm"
        ],
        top_layer=CLTFLayer(
            parameters["mu"],
            parameters["sigma"],
            parameters["R_top"],
            top_thickness_mm,
        ),
        bottom_layer=CLTFLayer(
            parameters["mu"],
            parameters["sigma"],
            parameters["R_bottom"],
            bottom_thickness_mm,
        ),
        decay_rate_day=parameters["k"],
        application_rate_g_ha=application_rate_g_ha,
        top_bulk_density_g_cm3=prepared.top_bulk_density_g_cm3,
        bottom_bulk_density_g_cm3=prepared.bottom_bulk_density_g_cm3,
        effective_porosity=settings.effective_porosity,
        method=settings.method,
        n_steps=settings.n_steps,
        rel_tol=settings.rel_tol,
    )
    return pd.concat(
        [prepared.forcing.loc[:, ["date"]].reset_index(drop=True), simulation],
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
    bottom_thickness = bottom_depth - top_depth
    application_rate = (
        float(application_rate_g_ha)
        if application_rate_g_ha is not None
        else float(prepared.application_rate_g_ha)
    )
    calibration_observations = _calibration_observations(prepared.observations)
    fit = fit_cltf(
        observations=calibration_observations,
        forcing=prepared.forcing,
        application_rate_g_ha=application_rate,
        top_bulk_density_g_cm3=prepared.top_bulk_density_g_cm3,
        bottom_bulk_density_g_cm3=prepared.bottom_bulk_density_g_cm3,
        lower=resolved.lower,
        upper=resolved.upper,
        initial=resolved.initial,
        starts=resolved.starts,
        n_starts=resolved.n_starts,
        seed=resolved.seed,
        top_thickness_mm=top_depth,
        bottom_thickness_mm=bottom_thickness,
        effective_porosity=resolved.effective_porosity,
        method=resolved.method,
        n_steps=resolved.n_steps,
        rel_tol=resolved.rel_tol,
        penalty=resolved.penalty,
        control=resolved.control,
    )
    predictions = _simulate_full_period(
        prepared,
        resolved,
        fit.parameters,
        application_rate,
        top_depth,
        bottom_thickness,
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
        "bottom_thickness_mm": bottom_thickness,
        "convolution_method": resolved.method,
        "convolution_steps": resolved.n_steps,
        "objective": fit.objective,
        "convergence": fit.convergence,
        "message": fit.message,
        "transport_scales": fit.transport_scales,
        "identifiability_note": fit.identifiability_note,
        "objective_profiles": objective_profiles,
    }
    return RunResult(
        parameters=fit.parameters,
        predictions=predictions,
        fit=fit,
        assessment=assessment,
        warnings=[],
        metadata=metadata,
    )
