"""Plotting helpers for the herbicide workbench."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def configure_matplotlib() -> None:
    plt.rcParams["font.family"] = "Arial"
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.spines.right"] = False


def plot_forcing(climate: pd.DataFrame):
    configure_matplotlib()
    fig, ax = plt.subplots(figsize=(9, 3.8), constrained_layout=True)
    ax.bar(climate["date"], climate["rain_mm"], color="#4C78A8", width=1.0, label="Rain")
    ax.plot(climate["date"], climate["et0_mm"], color="#D1495B", linewidth=1.8, label="ET0")
    ax.set_ylabel("Rain / ET0 (mm d-1)")
    ax2 = ax.twinx()
    ax2.plot(
        climate["date"],
        climate["cumulative_infiltration_mm"],
        color="#2A9D8F",
        linestyle="--",
        linewidth=1.8,
        label="Cumulative infiltration",
    )
    ax2.set_ylabel("Cumulative infiltration (mm)")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc="upper left", frameon=True)
    ax.set_xlabel("Date")
    return fig


def plot_observed_vs_model(observations: pd.DataFrame, predictions: pd.DataFrame, top_depth_mm: float):
    configure_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True, sharey=False)
    panels = [
        ("Top layer", top_depth_mm, "top_rel_conc"),
        ("Subsoil", None, "subsoil_rel_conc"),
    ]
    for ax, (title, depth, pred_col) in zip(axes, panels):
        if depth is None:
            obs = observations.loc[observations["depth_mm"] != top_depth_mm]
        else:
            obs = observations.loc[observations["depth_mm"] == top_depth_mm]
        if not obs.empty:
            ax.scatter(
                obs["days_since_application"],
                obs["relative_concentration"],
                color="#222222",
                alpha=0.65,
                label="Observed replicates",
            )
            mean_obs = (
                obs.groupby("days_since_application", as_index=False)
                .agg(relative_concentration=("relative_concentration", "mean"))
                .sort_values("days_since_application")
            )
            ax.plot(
                mean_obs["days_since_application"],
                mean_obs["relative_concentration"],
                color="#111111",
                marker="o",
                linewidth=1.5,
                label="Observed mean",
            )
        for run_type, group in predictions.groupby("run_type"):
            ax.plot(
                group["days_since_application"],
                group[pred_col],
                linewidth=1.9,
                label=f"Model {run_type}",
            )
        ax.set_title(title)
        ax.set_xlabel("Days since application")
        ax.set_ylabel("Relative concentration")
        ax.legend(frameon=True)
    return fig
