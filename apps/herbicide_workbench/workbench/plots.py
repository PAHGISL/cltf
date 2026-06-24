#!/usr/bin/env python3
"""
Script: plots.py
Objective: Wrap Python CLTF diagnostic plots for the Streamlit workbench.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: CLTF forcing, prediction, simulation, profile, and bulk-density tables.
Outputs: Matplotlib Figure objects for app rendering.
Usage: Import plotting helpers from workbench.plots.
Dependencies: matplotlib, pandas, cltf, workbench
"""

from __future__ import annotations

from matplotlib import font_manager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from workbench.config import ensure_cltf_path

ensure_cltf_path()
import cltf.plotting as cltf_plotting  # noqa: E402


ASSESSMENT_LABEL = "Residue assessment"
ASSESSMENT_COLOR = "#7A0177"
_COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7")
_ARIAL_REGISTERED = False


def _preferred_font_family() -> str:
    return "Arial"


def _register_arial_font() -> None:
    global _ARIAL_REGISTERED

    if _ARIAL_REGISTERED:
        return
    installed = {font.name for font in font_manager.fontManager.ttflist}
    if "Arial" not in installed:
        for font_path in font_manager.findSystemFonts(fontext="ttf"):
            if font_path.lower().endswith("arial.ttf"):
                font_manager.fontManager.addfont(font_path)
                break
    _ARIAL_REGISTERED = True


def configure_matplotlib() -> None:
    """Apply app-level matplotlib defaults."""

    _register_arial_font()
    plt.rcParams["font.family"] = _preferred_font_family()
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def _require_columns(
    data: pd.DataFrame,
    columns: tuple[str, ...],
    object_name: str,
) -> None:
    missing = sorted(set(columns).difference(data.columns))
    if missing:
        raise ValueError(
            f"{object_name} is missing columns: {', '.join(missing)}"
        )


def _layer_label(depth_top_mm: object, depth_bottom_mm: object) -> str:
    return f"{float(depth_top_mm):g}\N{EN DASH}{float(depth_bottom_mm):g} mm"


def _forcing_x_values(
    forcing: pd.DataFrame,
) -> tuple[pd.Series, str, bool]:
    if "date" in forcing.columns:
        return pd.to_datetime(forcing["date"]), "Date", True
    if "time_days" in forcing.columns:
        return forcing["time_days"], "Elapsed time (days)", False
    raise ValueError("forcing must contain date or time_days")


def add_assessment_line(
    axis: Axes,
    assessment_value: object,
    x_is_date: bool = False,
) -> None:
    """Add the approved vertical residue-assessment marker to one axis."""

    x_value = (
        pd.Timestamp(assessment_value)
        if x_is_date
        else assessment_value
    )
    axis.axvline(
        x_value,
        color=ASSESSMENT_COLOR,
        linestyle="--",
        linewidth=1.8,
        label=ASSESSMENT_LABEL,
    )


def _add_assessment_to_figure(
    figure: Figure,
    assessment_value: object | None,
    x_is_date: bool = False,
) -> Figure:
    if assessment_value is None:
        return figure
    for axis in figure.axes:
        add_assessment_line(axis, assessment_value, x_is_date=x_is_date)
    return figure


def plot_climate_forcing(
    forcing: pd.DataFrame,
    assessment_day: int | float | None = None,
    assessment_date: object | None = None,
) -> Figure:
    """Plot climate forcing and mark the residue assessment date/day."""

    configure_matplotlib()
    figure = cltf_plotting.plot_climate_forcing(forcing)
    if assessment_date is not None and "date" in forcing.columns:
        return _add_assessment_to_figure(
            figure,
            assessment_date,
            x_is_date=True,
        )
    return _add_assessment_to_figure(figure, assessment_day)


def plot_water_forcing(
    forcing: pd.DataFrame,
    assessment_day: int | float | None = None,
    assessment_date: object | None = None,
) -> Figure:
    """Plot daily rain, PET, and infiltration on one forcing axis."""

    configure_matplotlib()
    _require_columns(
        forcing,
        ("rain_mm", "pet_mm", "daily_infiltration_mm"),
        "forcing",
    )
    x_values, x_label, x_is_date = _forcing_x_values(forcing)
    figure, axis = plt.subplots(figsize=(8.5, 3.6), constrained_layout=True)
    axis.bar(
        x_values,
        forcing["rain_mm"],
        color="#0072B2",
        alpha=0.60,
        label="Rain",
    )
    axis.plot(
        x_values,
        forcing["pet_mm"],
        color="#D55E00",
        linewidth=1.8,
        label="PET",
    )
    axis.plot(
        x_values,
        forcing["daily_infiltration_mm"],
        color="#009E73",
        linewidth=1.8,
        label="Daily infiltration",
    )
    axis.set_xlabel(x_label)
    axis.set_ylabel("Daily water (mm)")
    axis.legend(frameon=False, ncols=3, fontsize=9)
    if assessment_date is not None and x_is_date:
        add_assessment_line(axis, assessment_date, x_is_date=True)
    elif assessment_day is not None:
        add_assessment_line(axis, assessment_day)
    return figure


def plot_cumulative_infiltration_histogram(
    forcing: pd.DataFrame,
) -> Figure:
    """Plot the distribution of cumulative infiltration as a histogram."""

    configure_matplotlib()
    _require_columns(forcing, ("cumulative_infiltration_mm",), "forcing")
    values = forcing["cumulative_infiltration_mm"].to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("forcing contains no finite cumulative infiltration")

    bin_count = min(30, max(6, int(np.sqrt(values.size))))
    figure, axis = plt.subplots(figsize=(8.5, 3.6), constrained_layout=True)
    axis.hist(
        values,
        bins=bin_count,
        color="#009E73",
        alpha=0.78,
        edgecolor="#ffffff",
    )
    axis.set_xlabel("Cumulative infiltration (mm)")
    axis.set_ylabel("Number of days")
    return figure


def plot_observed_fitted(
    predictions: pd.DataFrame,
    assessment_day: int | float | None = None,
) -> Figure:
    """Plot replicate observations, fitted values, and an assessment marker."""

    configure_matplotlib()
    figure = cltf_plotting.plot_observed_fitted(predictions)
    return _add_assessment_to_figure(figure, assessment_day)


def _violin_values(values: np.ndarray) -> np.ndarray:
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0:
        return values
    if values.size >= 2 and np.nanmax(values) > np.nanmin(values):
        return values
    center = float(values[0])
    spread = max(center * 0.015, 1e-9)
    return np.array([center - spread, center, center + spread])


def plot_observation_violin(
    predictions: pd.DataFrame,
    assessment_day: int | float | None = None,
) -> Figure:
    """Plot observation violins with jittered replicates and dashed fitted lines."""

    configure_matplotlib()
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
        raise ValueError("predictions contain no positive concentrations")

    data = predictions.copy()
    data["layer"] = [
        _layer_label(top, bottom)
        for top, bottom in zip(data["depth_top_mm"], data["depth_bottom_mm"])
    ]
    layer_order = list(dict.fromkeys(data["layer"].astype(str)))
    days = np.sort(data["days_since_application"].unique().astype(float))
    if days.size > 1:
        day_step = float(np.min(np.diff(days)))
        offset_width = max(day_step * 0.08, 0.75)
    else:
        offset_width = 0.75
    layer_offsets = {
        layer: (index - (len(layer_order) - 1) / 2.0) * offset_width
        for index, layer in enumerate(layer_order)
    }
    colors = {
        layer: _COLORS[index % len(_COLORS)]
        for index, layer in enumerate(layer_order)
    }

    figure, axis = plt.subplots(figsize=(8.5, 4.6), constrained_layout=True)
    rng = np.random.default_rng(20260624)
    for layer in layer_order:
        layer_data = data.loc[data["layer"].eq(layer)]
        for day, day_data in layer_data.groupby("days_since_application"):
            observed = day_data["analysis_concentration_ug_kg"].to_numpy(dtype=float)
            violin_values = _violin_values(observed)
            if violin_values.size == 0:
                continue
            position = float(day) + layer_offsets[layer]
            parts = axis.violinplot(
                [violin_values],
                positions=[position],
                widths=max(offset_width * 0.75, 0.25),
                showmeans=False,
                showmedians=False,
                showextrema=False,
            )
            for body in parts["bodies"]:
                body.set_facecolor(colors[layer])
                body.set_edgecolor(colors[layer])
                body.set_alpha(0.22)

            observed = observed[np.isfinite(observed) & (observed > 0)]
            jitter = rng.normal(0.0, max(offset_width * 0.07, 0.03), observed.size)
            axis.scatter(
                np.full(observed.size, position) + jitter,
                observed,
                color=colors[layer],
                edgecolors="#ffffff",
                linewidths=0.4,
                s=28,
                alpha=0.88,
                zorder=3,
            )

        fitted = (
            layer_data.groupby("days_since_application", as_index=False)[
                "predicted_concentration_ug_kg"
            ]
            .mean()
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
            linestyle="--",
            linewidth=2,
            label=f"{layer} fitted",
        )

    axis.set_yscale("log")
    axis.set_xlabel("Days since application")
    axis.set_ylabel("Resident concentration (\N{MICRO SIGN}g/kg)")
    axis.legend(
        handles=[
            Line2D(
                [0],
                [0],
                color=colors[layer],
                linestyle="--",
                linewidth=2,
                label=f"{layer} fitted",
            )
            for layer in layer_order
        ],
        frameon=False,
        fontsize=9,
    )
    if assessment_day is not None:
        add_assessment_line(axis, assessment_day)
    return figure


def _time_edges(time_values: np.ndarray) -> np.ndarray:
    if time_values.size == 1:
        return np.array([time_values[0] - 0.5, time_values[0] + 0.5])
    midpoints = (time_values[:-1] + time_values[1:]) / 2.0
    first = time_values[0] - (time_values[1] - time_values[0]) / 2.0
    last = time_values[-1] + (time_values[-1] - time_values[-2]) / 2.0
    return np.concatenate(([first], midpoints, [last]))


def plot_simulation_heatmap(
    simulation: pd.DataFrame,
    top_depth_mm: float,
    bottom_depth_mm: float,
    assessment_day: int | float | None = None,
) -> Figure:
    """Plot simulated top/bottom resident concentration as a depth heatmap."""

    configure_matplotlib()
    _require_columns(
        simulation,
        (
            "time_days",
            "concentration_top_ug_kg",
            "concentration_bottom_ug_kg",
        ),
        "simulation",
    )
    ordered = simulation.sort_values("time_days")
    time_values = ordered["time_days"].to_numpy(dtype=float)
    concentration = np.vstack(
        [
            ordered["concentration_top_ug_kg"].to_numpy(dtype=float),
            ordered["concentration_bottom_ug_kg"].to_numpy(dtype=float),
        ]
    )
    concentration[~np.isfinite(concentration)] = np.nan
    x_edges = _time_edges(time_values)
    y_edges = np.array([0.0, float(top_depth_mm), float(bottom_depth_mm)])

    figure, axis = plt.subplots(figsize=(8.5, 4.5), constrained_layout=True)
    mesh = axis.pcolormesh(
        x_edges,
        y_edges,
        concentration,
        cmap="YlOrRd",
        shading="flat",
    )
    axis.set_ylim(float(bottom_depth_mm), 0.0)
    axis.set_xlabel("Days since application")
    axis.set_ylabel("Soil depth (mm)")
    axis.set_yticks([
        float(top_depth_mm) / 2.0,
        (float(top_depth_mm) + float(bottom_depth_mm)) / 2.0,
    ])
    axis.set_yticklabels([
        f"0\N{EN DASH}{float(top_depth_mm):g}",
        f"{float(top_depth_mm):g}\N{EN DASH}{float(bottom_depth_mm):g}",
    ])
    if assessment_day is not None:
        add_assessment_line(axis, assessment_day)
    colorbar = figure.colorbar(
        mesh,
        ax=axis,
        orientation="horizontal",
        pad=0.16,
        fraction=0.08,
    )
    colorbar.set_label("Resident concentration (\N{MICRO SIGN}g/kg)")
    return figure


def plot_residuals(predictions: pd.DataFrame) -> Figure:
    """Plot CLTF residuals against fitted concentration."""

    configure_matplotlib()
    return cltf_plotting.plot_residuals(predictions)


def plot_mass_fractions(
    simulation: pd.DataFrame,
    assessment_day: int | float | None = None,
) -> Figure:
    """Plot CLTF mass fractions and mark the assessment day."""

    configure_matplotlib()
    figure = cltf_plotting.plot_mass_fractions(simulation)
    return _add_assessment_to_figure(figure, assessment_day)


def plot_mass_balance(
    simulation: pd.DataFrame,
    assessment_day: int | float | None = None,
) -> Figure:
    """Plot numerical mass-balance error and mark the assessment day."""

    configure_matplotlib()
    figure = cltf_plotting.plot_mass_balance(simulation)
    return _add_assessment_to_figure(figure, assessment_day)


def plot_objective_profiles(profile: pd.DataFrame) -> Figure:
    """Plot CLTF objective profiles."""

    configure_matplotlib()
    return cltf_plotting.plot_objective_profile(profile)


def plot_bulk_density(bulk_density: pd.DataFrame) -> Figure:
    """Plot SLGA bulk-density estimates and intervals."""

    configure_matplotlib()
    return cltf_plotting.plot_bulk_density(bulk_density)
