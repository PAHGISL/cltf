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

from matplotlib.axes import Axes
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import pandas as pd

from workbench.config import ensure_cltf_path

ensure_cltf_path()
import cltf.plotting as cltf_plotting  # noqa: E402


ASSESSMENT_LABEL = "Residue assessment"
ASSESSMENT_COLOR = "#7A0177"


def configure_matplotlib() -> None:
    """Apply app-level matplotlib defaults."""

    plt.rcParams["font.family"] = "Arial"
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


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


def plot_observed_fitted(
    predictions: pd.DataFrame,
    assessment_day: int | float | None = None,
) -> Figure:
    """Plot replicate observations, fitted values, and an assessment marker."""

    configure_matplotlib()
    figure = cltf_plotting.plot_observed_fitted(predictions)
    return _add_assessment_to_figure(figure, assessment_day)


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
