#!/usr/bin/env python3
"""
Script: calibration.py
Objective: Fit the two-layer CLTF model to replicate-level log concentrations.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Observations, forcing, soil properties, starts, and parameter bounds.
Outputs: Multistart fits, predictions, bound flags, and objective profiles.
Usage: Import cltf_objective, fit_cltf, and profile_cltf_parameter.
Dependencies: dataclasses, math, numpy, pandas, scipy, cltf simulation
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .simulation import simulate_cltf
from .transport import CLTFLayer


_PARAMETER_NAMES = ("mu", "sigma", "R_top", "R_bottom", "k")


@dataclass(frozen=True)
class CLTFFit:
    """Result of deterministic multistart CLTF calibration."""

    parameters: dict[str, float]
    objective: float
    convergence: int
    message: str
    start_index: int
    bound_hit: dict[str, bool]
    predictions: pd.DataFrame
    all_starts: pd.DataFrame
    lower: dict[str, float]
    upper: dict[str, float]
    starts: np.ndarray
    transport_scales: dict[str, float]
    identifiability_note: str
    _context: dict[str, Any] = field(repr=False, compare=False)
    _penalty: float = field(repr=False, compare=False)
    _control: dict[str, Any] = field(repr=False, compare=False)


def _normalize_parameters(
    parameters: Mapping[str, float] | Sequence[float] | np.ndarray,
    argument: str = "parameters",
) -> dict[str, float]:
    if isinstance(parameters, Mapping):
        if not set(_PARAMETER_NAMES).issubset(parameters):
            raise ValueError(
                f"{argument} must contain named values: "
                f"{', '.join(_PARAMETER_NAMES)}"
            )
        result = {
            name: float(parameters[name])
            for name in _PARAMETER_NAMES
        }
    else:
        values = np.asarray(parameters, dtype=float)
        if values.ndim != 1 or len(values) != len(_PARAMETER_NAMES):
            raise ValueError(f"{argument} must contain five numeric values")
        result = dict(zip(_PARAMETER_NAMES, values.astype(float)))
    if not all(math.isfinite(value) for value in result.values()):
        raise ValueError(f"{argument} must be finite")
    return result


def _parameter_array(parameters: Mapping[str, float]) -> np.ndarray:
    return np.asarray([parameters[name] for name in _PARAMETER_NAMES], dtype=float)


def _validate_calibration_data(
    observations: pd.DataFrame,
    forcing: pd.DataFrame,
) -> None:
    observation_columns = {
        "days_since_application",
        "depth_top_mm",
        "depth_bottom_mm",
        "analysis_concentration_ug_kg",
    }
    forcing_columns = {"time_days", "cumulative_infiltration_mm"}
    missing_observations = observation_columns.difference(observations.columns)
    missing_forcing = forcing_columns.difference(forcing.columns)
    if missing_observations:
        raise ValueError(
            "observations are missing columns: "
            f"{', '.join(sorted(missing_observations))}"
        )
    if missing_forcing:
        raise ValueError(
            f"forcing is missing columns: {', '.join(sorted(missing_forcing))}"
        )
    if forcing["time_days"].duplicated().any():
        raise ValueError("forcing time_days values must be unique")


def _predict_concentrations(
    parameters: Mapping[str, float] | Sequence[float] | np.ndarray,
    observations: pd.DataFrame,
    forcing: pd.DataFrame,
    application_rate_g_ha: float,
    top_bulk_density_g_cm3: float,
    bottom_bulk_density_g_cm3: float,
    top_thickness_mm: float = 100.0,
    bottom_thickness_mm: float = 200.0,
    effective_porosity: float = 0.2,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 1001,
    rel_tol: float = 1e-8,
) -> np.ndarray:
    _validate_calibration_data(observations, forcing)
    values = _normalize_parameters(parameters)
    observation_times = np.sort(
        observations["days_since_application"].unique().astype(float)
    )
    forcing_lookup = forcing.set_index("time_days")
    if not np.all(np.isin(observation_times, forcing_lookup.index.to_numpy())):
        raise ValueError("Every observation time must occur in forcing time_days")
    simulation_forcing = forcing_lookup.loc[observation_times].reset_index()

    simulation = simulate_cltf(
        time_days=simulation_forcing["time_days"],
        cumulative_infiltration_mm=simulation_forcing[
            "cumulative_infiltration_mm"
        ],
        top_layer=CLTFLayer(
            values["mu"],
            values["sigma"],
            values["R_top"],
            top_thickness_mm,
        ),
        bottom_layer=CLTFLayer(
            values["mu"],
            values["sigma"],
            values["R_bottom"],
            bottom_thickness_mm,
        ),
        decay_rate_day=values["k"],
        application_rate_g_ha=application_rate_g_ha,
        top_bulk_density_g_cm3=top_bulk_density_g_cm3,
        bottom_bulk_density_g_cm3=bottom_bulk_density_g_cm3,
        effective_porosity=effective_porosity,
        method=method,
        n_steps=n_steps,
        rel_tol=rel_tol,
    ).set_index("time_days")

    tolerance = math.sqrt(np.finfo(float).eps)
    depth_top = observations["depth_top_mm"].to_numpy(dtype=float)
    depth_bottom = observations["depth_bottom_mm"].to_numpy(dtype=float)
    is_top = (
        np.abs(depth_top) <= tolerance
    ) & (
        np.abs(depth_bottom - top_thickness_mm) <= tolerance
    )
    is_bottom = (
        np.abs(depth_top - top_thickness_mm) <= tolerance
    ) & (
        np.abs(
            depth_bottom - top_thickness_mm - bottom_thickness_mm
        )
        <= tolerance
    )
    if np.any(~is_top & ~is_bottom):
        raise ValueError(
            "Observation intervals must match the configured top or bottom "
            "model layer"
        )

    times = observations["days_since_application"].to_numpy(dtype=float)
    prediction = np.empty(len(observations), dtype=float)
    prediction[is_top] = simulation.loc[
        times[is_top],
        "concentration_top_ug_kg",
    ].to_numpy()
    prediction[is_bottom] = simulation.loc[
        times[is_bottom],
        "concentration_bottom_ug_kg",
    ].to_numpy()
    return prediction


def cltf_objective(
    parameters: Mapping[str, float] | Sequence[float] | np.ndarray,
    observations: pd.DataFrame,
    forcing: pd.DataFrame,
    application_rate_g_ha: float,
    top_bulk_density_g_cm3: float,
    bottom_bulk_density_g_cm3: float,
    top_thickness_mm: float = 100.0,
    bottom_thickness_mm: float = 200.0,
    effective_porosity: float = 0.2,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 1001,
    rel_tol: float = 1e-8,
    penalty: float = 1e6,
) -> float:
    """Calculate replicate-level root mean squared log residuals."""

    try:
        prediction = _predict_concentrations(
            parameters,
            observations,
            forcing,
            application_rate_g_ha,
            top_bulk_density_g_cm3,
            bottom_bulk_density_g_cm3,
            top_thickness_mm,
            bottom_thickness_mm,
            effective_porosity,
            method,
            n_steps,
            rel_tol,
        )
        observed = observations[
            "analysis_concentration_ug_kg"
        ].to_numpy(dtype=float)
        keep = np.isfinite(observed) & (observed > 0)
        if (
            not np.any(keep)
            or np.any(~np.isfinite(prediction[keep]))
            or np.any(prediction[keep] <= 0)
        ):
            return float(penalty)
        result = float(
            np.sqrt(
                np.mean(
                    (
                        np.log(observed[keep])
                        - np.log(prediction[keep])
                    )
                    ** 2
                )
            )
        )
    except Exception:
        return float(penalty)
    return min(result, float(penalty)) if math.isfinite(result) else float(penalty)


def _generate_starts(
    initial: dict[str, float],
    lower: dict[str, float],
    upper: dict[str, float],
    n_starts: int,
    seed: int,
) -> np.ndarray:
    if not isinstance(n_starts, int) or n_starts < 1:
        raise ValueError("n_starts must be a positive integer")
    lower_values = _parameter_array(lower)
    upper_values = _parameter_array(upper)
    starts = np.empty((n_starts, len(_PARAMETER_NAMES)), dtype=float)
    starts[0] = _parameter_array(initial)
    if n_starts > 1:
        rng = np.random.default_rng(seed)
        starts[1:] = rng.uniform(
            lower_values,
            upper_values,
            size=(n_starts - 1, len(_PARAMETER_NAMES)),
        )
    return starts


def _bound_hits(
    parameters: dict[str, float],
    lower: dict[str, float],
    upper: dict[str, float],
    tolerance: float,
) -> dict[str, bool]:
    result = {}
    for name in _PARAMETER_NAMES:
        scale = max(
            1.0,
            abs(lower[name]),
            abs(upper[name]),
            abs(upper[name] - lower[name]),
        )
        result[name] = bool(
            abs(parameters[name] - lower[name]) <= tolerance * scale
            or abs(parameters[name] - upper[name]) <= tolerance * scale
        )
    return result


def _scipy_options(control: Mapping[str, Any] | None) -> dict[str, Any]:
    options = dict(control or {"maxit": 500})
    if "maxit" in options:
        options["maxiter"] = options.pop("maxit")
    return options


def fit_cltf(
    observations: pd.DataFrame,
    forcing: pd.DataFrame,
    application_rate_g_ha: float,
    top_bulk_density_g_cm3: float,
    bottom_bulk_density_g_cm3: float,
    lower: Mapping[str, float] | Sequence[float] = (
        0.05,
        0.05,
        0.1,
        0.1,
        0.0,
    ),
    upper: Mapping[str, float] | Sequence[float] = (
        10.0,
        3.0,
        100.0,
        100.0,
        0.1,
    ),
    initial: Mapping[str, float] | Sequence[float] = (
        1.0,
        0.5,
        2.0,
        3.0,
        0.005,
    ),
    starts: np.ndarray | pd.DataFrame | None = None,
    n_starts: int = 6,
    seed: int = 42,
    top_thickness_mm: float = 100.0,
    bottom_thickness_mm: float = 200.0,
    effective_porosity: float = 0.2,
    method: Literal["adaptive", "trapezoid"] = "adaptive",
    n_steps: int = 1001,
    rel_tol: float = 1e-8,
    penalty: float = 1e6,
    bound_tolerance: float = 1e-6,
    control: Mapping[str, Any] | None = None,
) -> CLTFFit:
    """Fit the CLTF model with deterministic multistart optimization."""

    _validate_calibration_data(observations, forcing)
    lower_values = _normalize_parameters(lower, "lower")
    upper_values = _normalize_parameters(upper, "upper")
    initial_values = _normalize_parameters(initial, "initial")
    lower_array = _parameter_array(lower_values)
    upper_array = _parameter_array(upper_values)
    initial_array = _parameter_array(initial_values)
    if np.any(lower_array >= upper_array):
        raise ValueError(
            "Every lower parameter bound must be below its upper bound"
        )
    if np.any(initial_array < lower_array) or np.any(initial_array > upper_array):
        raise ValueError("initial parameters must lie within bounds")

    if starts is None:
        start_values = _generate_starts(
            initial_values,
            lower_values,
            upper_values,
            n_starts,
            seed,
        )
    elif isinstance(starts, pd.DataFrame):
        if not set(_PARAMETER_NAMES).issubset(starts.columns):
            raise ValueError("starts must contain five parameter columns")
        start_values = starts.loc[:, _PARAMETER_NAMES].to_numpy(dtype=float)
    else:
        start_values = np.asarray(starts, dtype=float)
        if start_values.ndim != 2 or start_values.shape[1] != len(_PARAMETER_NAMES):
            raise ValueError("starts must contain five parameter columns")
    if (
        not np.all(np.isfinite(start_values))
        or np.any(start_values < lower_array)
        or np.any(start_values > upper_array)
    ):
        raise ValueError("All starts must be finite and lie within bounds")

    context = {
        "observations": observations,
        "forcing": forcing,
        "application_rate_g_ha": application_rate_g_ha,
        "top_bulk_density_g_cm3": top_bulk_density_g_cm3,
        "bottom_bulk_density_g_cm3": bottom_bulk_density_g_cm3,
        "top_thickness_mm": top_thickness_mm,
        "bottom_thickness_mm": bottom_thickness_mm,
        "effective_porosity": effective_porosity,
        "method": method,
        "n_steps": n_steps,
        "rel_tol": rel_tol,
    }

    def objective(parameter_array: np.ndarray) -> float:
        return cltf_objective(
            parameter_array,
            **context,
            penalty=penalty,
        )

    options = _scipy_options(control)
    results = []
    for start in start_values:
        try:
            result = minimize(
                objective,
                start,
                method="L-BFGS-B",
                bounds=list(zip(lower_array, upper_array)),
                options=options,
            )
        except Exception as error:
            result = type(
                "FailedOptimization",
                (),
                {
                    "x": start,
                    "fun": float(penalty),
                    "status": 100,
                    "message": str(error),
                },
            )()
        results.append(result)

    objectives = np.asarray([float(result.fun) for result in results])
    best_index_zero = int(np.argmin(objectives))
    best = results[best_index_zero]
    parameters = _normalize_parameters(best.x)

    start_rows = []
    for index, (start, result) in enumerate(
        zip(start_values, results),
        start=1,
    ):
        row: dict[str, object] = {
            "start_index": index,
            "objective": float(result.fun),
            "convergence": int(result.status),
            "message": str(result.message or ""),
        }
        for parameter_index, name in enumerate(_PARAMETER_NAMES):
            row[f"start_{name}"] = start[parameter_index]
            row[f"fitted_{name}"] = result.x[parameter_index]
        start_rows.append(row)

    prediction = _predict_concentrations(parameters, **context)
    predictions = observations.copy()
    predictions["predicted_concentration_ug_kg"] = prediction
    observed = predictions["analysis_concentration_ug_kg"].to_numpy(dtype=float)
    keep = (
        np.isfinite(observed)
        & (observed > 0)
        & np.isfinite(prediction)
        & (prediction > 0)
    )
    log_residual = np.full(len(predictions), np.nan)
    log_residual[keep] = np.log(observed[keep]) - np.log(prediction[keep])
    predictions["log_residual"] = log_residual

    return CLTFFit(
        parameters=parameters,
        objective=float(best.fun),
        convergence=int(best.status),
        message=str(best.message or ""),
        start_index=best_index_zero + 1,
        bound_hit=_bound_hits(
            parameters,
            lower_values,
            upper_values,
            bound_tolerance,
        ),
        predictions=predictions,
        all_starts=pd.DataFrame(start_rows),
        lower=lower_values,
        upper=upper_values,
        starts=start_values.copy(),
        transport_scales={
            "top": parameters["mu"] * parameters["R_top"],
            "bottom": parameters["mu"] * parameters["R_bottom"],
        },
        identifiability_note=(
            "The current CLTF equations identify the products mu * R_top "
            "and mu * R_bottom, not mu and both retardation factors separately."
        ),
        _context=context,
        _penalty=float(penalty),
        _control=options,
    )


def profile_cltf_parameter(
    fit: CLTFFit,
    parameter: str,
    grid: Sequence[float] | np.ndarray,
    control: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    """Profile one fitted parameter while re-optimizing the others."""

    if not isinstance(fit, CLTFFit):
        raise ValueError("fit must be returned by fit_cltf")
    if parameter not in _PARAMETER_NAMES:
        raise ValueError("parameter must name one fitted CLTF parameter")
    grid_values = np.atleast_1d(np.asarray(grid, dtype=float))
    if (
        len(grid_values) == 0
        or not np.all(np.isfinite(grid_values))
        or np.any(grid_values < fit.lower[parameter])
        or np.any(grid_values > fit.upper[parameter])
    ):
        raise ValueError(
            "grid must contain finite values within the parameter bounds"
        )

    remaining = [name for name in _PARAMETER_NAMES if name != parameter]
    lower = np.asarray([fit.lower[name] for name in remaining])
    upper = np.asarray([fit.upper[name] for name in remaining])
    initial = np.asarray([fit.parameters[name] for name in remaining])
    options = _scipy_options(control) if control is not None else fit._control
    rows: list[dict[str, object]] = []

    for fixed_value in grid_values:

        def objective(free_parameters: np.ndarray) -> float:
            parameters = fit.parameters.copy()
            parameters[parameter] = float(fixed_value)
            parameters.update(
                {
                    name: float(value)
                    for name, value in zip(remaining, free_parameters)
                }
            )
            return cltf_objective(
                parameters,
                **fit._context,
                penalty=fit._penalty,
            )

        try:
            result = minimize(
                objective,
                initial,
                method="L-BFGS-B",
                bounds=list(zip(lower, upper)),
                options=options,
            )
        except Exception as error:
            result = type(
                "FailedOptimization",
                (),
                {
                    "x": initial,
                    "fun": fit._penalty,
                    "status": 100,
                    "message": str(error),
                },
            )()
        parameters = fit.parameters.copy()
        parameters[parameter] = float(fixed_value)
        parameters.update(
            {
                name: float(value)
                for name, value in zip(remaining, result.x)
            }
        )
        row: dict[str, object] = {
            "parameter": parameter,
            "parameter_value": float(fixed_value),
            "objective": float(result.fun),
            "convergence": int(result.status),
            "message": str(result.message or ""),
        }
        row.update(parameters)
        rows.append(row)

    return pd.DataFrame(rows)
