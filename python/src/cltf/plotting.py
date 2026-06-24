#!/usr/bin/env python3
"""
Script: plotting.py
Objective: Produce matplotlib diagnostics for CLTF inputs, fits, and mass balance.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Climate, soil, prediction, simulation, and profile tables.
Outputs: Matplotlib Figure objects.
Usage: Import plotting functions from cltf or cltf.plotting.
Dependencies: math, matplotlib, numpy, pandas
"""

from __future__ import annotations

import math
from typing import Sequence

import matplotlib
from matplotlib import font_manager
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _preferred_font_family() -> str:
    available = {
        font.name
        for font in font_manager.fontManager.ttflist
    }
    return "Arial" if "Arial" in available else "DejaVu Sans"


matplotlib.rcParams["font.family"] = [_preferred_font_family()]

_COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")
_MASS_COLORS = ("#0072B2", "#D55E00", "#009E73", "#777777")


def _require_columns(
    data: pd.DataFrame,
    columns: Sequence[str],
    object_name: str,
) -> None:
    missing = set(columns).difference(data.columns)
    if missing:
        raise ValueError(
            f"{object_name} is missing columns: {', '.join(sorted(missing))}"
        )


def _layer_label(depth_top_mm: object, depth_bottom_mm: object) -> str:
    return f"{float(depth_top_mm):g}\N{EN DASH}{float(depth_bottom_mm):g} mm"


def _new_figure(
    nrows: int = 1,
    ncols: int = 1,
    figsize: tuple[float, float] = (8.0, 5.2),
) -> tuple[Figure, object]:
    return plt.subplots(
        nrows=nrows,
        ncols=ncols,
        figsize=figsize,
        constrained_layout=True,
    )


def plot_climate_forcing(forcing: pd.DataFrame) -> Figure:
    """Plot daily rain/PET and cumulative infiltration."""

    _require_columns(
        forcing,
        (
            "rain_mm",
            "pet_mm",
            "daily_infiltration_mm",
            "cumulative_infiltration_mm",
        ),
        "forcing",
    )
    if "date" in forcing:
        x = pd.to_datetime(forcing["date"])
        x_label = "Date"
    elif "time_days" in forcing:
        x = forcing["time_days"]
        x_label = "Elapsed time (days)"
    else:
        raise ValueError("forcing must contain date or time_days")

    figure, axes = _new_figure(2, 1, figsize=(8.5, 7.0))
    top, bottom = axes
    top.vlines(
        x,
        0,
        forcing["rain_mm"],
        color="#0072B2",
        linewidth=4,
        label="Rain",
    )
    top.plot(
        x,
        forcing["pet_mm"],
        color="#D55E00",
        linewidth=1.8,
        label="PET",
    )
    top.set_ylabel("Daily water (mm)")
    top.legend(frameon=False)

    bottom.plot(
        x,
        forcing["cumulative_infiltration_mm"],
        color="#009E73",
        linewidth=2,
    )
    positive = forcing["daily_infiltration_mm"].to_numpy(dtype=float) > 0
    bottom.scatter(
        np.asarray(x)[positive],
        forcing.loc[positive, "cumulative_infiltration_mm"],
        color="#009E73",
        s=22,
    )
    bottom.set_xlabel(x_label)
    bottom.set_ylabel("Cumulative infiltration (mm)")
    return figure


def _geometric_plot_summary(predictions: pd.DataFrame) -> pd.DataFrame:
    usable = predictions.loc[
        np.isfinite(predictions["analysis_concentration_ug_kg"])
        & predictions["analysis_concentration_ug_kg"].gt(0)
    ].copy()
    groups = [
        "days_since_application",
        "depth_top_mm",
        "depth_bottom_mm",
    ]
    return (
        usable.groupby(groups, as_index=False, sort=True)[
            "analysis_concentration_ug_kg"
        ]
        .agg(lambda values: float(np.exp(np.mean(np.log(values)))))
        .rename(
            columns={
                "analysis_concentration_ug_kg": "geometric_mean_ug_kg"
            }
        )
    )


def plot_observed_fitted(predictions: pd.DataFrame) -> Figure:
    """Plot replicate observations, geometric means, and fitted concentrations."""

    _require_columns(
        predictions,
        (
            "days_since_application",
            "depth_top_mm",
            "depth_bottom_mm",
            "analysis_concentration_ug_kg",
            "predicted_concentration_ug_kg",
        ),
        "predictions",
    )
    positive = np.concatenate(
        (
            predictions["analysis_concentration_ug_kg"].to_numpy(dtype=float),
            predictions["predicted_concentration_ug_kg"].to_numpy(dtype=float),
        )
    )
    if not np.any(np.isfinite(positive) & (positive > 0)):
        raise ValueError(
            "predictions contain no positive concentrations to plot"
        )

    layers = [
        _layer_label(top, bottom)
        for top, bottom in zip(
            predictions["depth_top_mm"],
            predictions["depth_bottom_mm"],
        )
    ]
    layer_order = list(dict.fromkeys(layers))
    colors = {
        layer: _COLORS[index % len(_COLORS)]
        for index, layer in enumerate(layer_order)
    }
    geometric = _geometric_plot_summary(predictions)
    geometric["layer"] = [
        _layer_label(top, bottom)
        for top, bottom in zip(
            geometric["depth_top_mm"],
            geometric["depth_bottom_mm"],
        )
    ]

    figure, axis = _new_figure()
    for layer in layer_order:
        selected = np.asarray(layers) == layer
        layer_data = predictions.loc[selected]
        fitted = (
            layer_data[
                [
                    "days_since_application",
                    "predicted_concentration_ug_kg",
                ]
            ]
            .drop_duplicates()
            .sort_values("days_since_application")
        )
        fitted = fitted.loc[
            np.isfinite(fitted["predicted_concentration_ug_kg"])
            & fitted["predicted_concentration_ug_kg"].gt(0)
        ]
        axis.plot(
            fitted["days_since_application"],
            fitted["predicted_concentration_ug_kg"],
            color=colors[layer],
            linewidth=2,
        )
        observed = layer_data.loc[
            np.isfinite(layer_data["analysis_concentration_ug_kg"])
            & layer_data["analysis_concentration_ug_kg"].gt(0)
        ]
        axis.scatter(
            observed["days_since_application"],
            observed["analysis_concentration_ug_kg"],
            facecolors="none",
            edgecolors=colors[layer],
            s=30,
        )
        geometric_layer = geometric.loc[geometric["layer"].eq(layer)]
        axis.scatter(
            geometric_layer["days_since_application"],
            geometric_layer["geometric_mean_ug_kg"],
            color=colors[layer],
            s=26,
        )

    handles = [
        Line2D([0], [0], color=colors[layer], linewidth=2, label=f"{layer} fit")
        for layer in layer_order
    ]
    handles.extend(
        (
            Line2D(
                [0],
                [0],
                marker="o",
                linestyle="none",
                markerfacecolor="none",
                markeredgecolor="#333333",
                label="Replicate",
            ),
            Line2D(
                [0],
                [0],
                marker="o",
                linestyle="none",
                color="#333333",
                label="Geometric mean",
            ),
        )
    )
    axis.set_yscale("log")
    axis.set_xlabel("Days since application")
    axis.set_ylabel("Resident concentration (\N{MICRO SIGN}g/kg)")
    axis.legend(handles=handles, frameon=False, fontsize=9)
    return figure


def plot_residuals(predictions: pd.DataFrame) -> Figure:
    """Plot log residuals against fitted concentration."""

    _require_columns(
        predictions,
        (
            "depth_top_mm",
            "depth_bottom_mm",
            "analysis_concentration_ug_kg",
            "predicted_concentration_ug_kg",
        ),
        "predictions",
    )
    if "log_residual" in predictions:
        residual = predictions["log_residual"].to_numpy(dtype=float)
    else:
        residual = np.log(
            predictions["analysis_concentration_ug_kg"].to_numpy(dtype=float)
        ) - np.log(
            predictions["predicted_concentration_ug_kg"].to_numpy(dtype=float)
        )
    fitted = predictions["predicted_concentration_ug_kg"].to_numpy(dtype=float)
    usable = np.isfinite(residual) & np.isfinite(fitted) & (fitted > 0)
    if not np.any(usable):
        raise ValueError("predictions contain no finite log residuals")

    layers = np.asarray(
        [
            _layer_label(top, bottom)
            for top, bottom in zip(
                predictions["depth_top_mm"],
                predictions["depth_bottom_mm"],
            )
        ]
    )
    layer_order = list(dict.fromkeys(layers[usable]))
    figure, axis = _new_figure()
    for index, layer in enumerate(layer_order):
        selected = usable & (layers == layer)
        axis.scatter(
            fitted[selected],
            residual[selected],
            color=_COLORS[index % len(_COLORS)],
            s=28,
            label=layer,
        )
    axis.axhline(0, color="#666666", linestyle="--", linewidth=1)
    axis.set_xscale("log")
    axis.set_xlabel("Fitted concentration (\N{MICRO SIGN}g/kg, log scale)")
    axis.set_ylabel("Log(observed) - log(fitted)")
    axis.legend(frameon=False)
    return figure


def plot_mass_fractions(simulation: pd.DataFrame) -> Figure:
    """Plot top, bottom, below-profile, and degraded mass fractions."""

    mass_columns = ("mass_top", "mass_bottom", "mass_below", "mass_degraded")
    _require_columns(simulation, ("time_days", *mass_columns), "simulation")
    labels = ("Top layer", "Bottom layer", "Below profile", "Degraded")
    figure, axis = _new_figure()
    for column, label, color in zip(mass_columns, labels, _MASS_COLORS):
        axis.plot(
            simulation["time_days"],
            simulation[column],
            color=color,
            linewidth=2,
            label=label,
        )
    axis.set_ylim(0, 1)
    axis.set_xlabel("Days since application")
    axis.set_ylabel("Applied-mass fraction")
    axis.legend(frameon=False)
    return figure


def plot_mass_balance(simulation: pd.DataFrame) -> Figure:
    """Plot numerical mass-balance error through time."""

    mass_columns = ("mass_top", "mass_bottom", "mass_below", "mass_degraded")
    _require_columns(simulation, ("time_days", *mass_columns), "simulation")
    deviation = simulation.loc[:, mass_columns].sum(axis=1) - 1.0
    limit = max(float(np.max(np.abs(deviation))), 1e-12)
    figure, axis = _new_figure()
    axis.plot(
        simulation["time_days"],
        deviation,
        color="#0072B2",
        linewidth=1.8,
    )
    axis.axhline(0, color="#666666", linestyle="--", linewidth=1)
    axis.set_ylim(-limit, limit)
    axis.set_xlabel("Days since application")
    axis.set_ylabel("Mass-balance error")
    return figure


def plot_objective_profile(profile: pd.DataFrame) -> Figure:
    """Plot one or more fitted objective profiles."""

    _require_columns(
        profile,
        ("parameter", "parameter_value", "objective"),
        "profile",
    )
    parameters = list(dict.fromkeys(profile["parameter"].astype(str)))
    ncols = min(2, len(parameters))
    nrows = math.ceil(len(parameters) / ncols)
    figure, axes = _new_figure(
        nrows,
        ncols,
        figsize=(7.0 * ncols, 4.8 * nrows),
    )
    axes_array = np.atleast_1d(axes).ravel()
    for axis, parameter in zip(axes_array, parameters):
        values = profile.loc[
            profile["parameter"].astype(str).eq(parameter)
        ].sort_values("parameter_value")
        axis.plot(
            values["parameter_value"],
            values["objective"],
            color="#0072B2",
            marker="o",
        )
        minimum = values.loc[values["objective"].idxmin(), "parameter_value"]
        axis.axvline(minimum, color="#D55E00", linestyle="--")
        axis.set_xlabel(parameter)
        axis.set_ylabel("Log-RMSE objective")
    for axis in axes_array[len(parameters):]:
        axis.set_visible(False)
    return figure


def plot_bulk_density(bulk_density: pd.DataFrame) -> Figure:
    """Plot SLGA bulk-density estimates and intervals by depth."""

    _require_columns(
        bulk_density,
        (
            "depth_top_mm",
            "depth_bottom_mm",
            "estimate_g_cm3",
            "lower_g_cm3",
            "upper_g_cm3",
        ),
        "bulk_density",
    )
    figure, axis = _new_figure()
    for row in bulk_density.itertuples(index=False):
        axis.add_patch(
            Rectangle(
                (row.lower_g_cm3, row.depth_top_mm),
                row.upper_g_cm3 - row.lower_g_cm3,
                row.depth_bottom_mm - row.depth_top_mm,
                facecolor="#0072B2",
                edgecolor="#0072B2",
                alpha=0.18,
            )
        )
        axis.plot(
            [row.estimate_g_cm3, row.estimate_g_cm3],
            [row.depth_top_mm, row.depth_bottom_mm],
            color="#D55E00",
            linewidth=2.5,
        )
    axis.set_xlim(
        bulk_density["lower_g_cm3"].min(),
        bulk_density["upper_g_cm3"].max(),
    )
    axis.set_ylim(
        bulk_density["depth_bottom_mm"].max(),
        bulk_density["depth_top_mm"].min(),
    )
    axis.set_xlabel("Bulk density (g/cm³)")
    axis.set_ylabel("Depth (mm)")
    axis.legend(
        handles=[
            Line2D(
                [0],
                [0],
                color="#D55E00",
                linewidth=2.5,
                label="Estimate",
            ),
            Patch(
                facecolor="#0072B2",
                edgecolor="#0072B2",
                alpha=0.18,
                label="SLGA interval",
            ),
        ],
        frameon=False,
    )
    return figure
