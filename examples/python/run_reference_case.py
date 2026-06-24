#!/usr/bin/env python3
"""
Script: run_reference_case.py
Objective: Build reproducible shared CLTF reference cases from normalized inputs.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared case JSON, observations, SILO forcing, and SLGA bulk density.
Outputs: Prepared CSV/JSON artifacts and seven diagnostic PNG plots.
Usage: python examples/python/run_reference_case.py --case CASE --input-dir DIR --output-dir DIR
Dependencies: argparse, hashlib, json, pathlib, pandas, numpy, matplotlib, cltf
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

REPOSITORY_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_DIR / "python" / "src"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cltf import (
    CLTFLayer,
    daily_infiltration,
    fit_cltf,
    infer_application_rate_g_ha,
    parse_silo_csv,
    parse_slga_bulk_density,
    pet_from_temperature,
    plot_bulk_density,
    plot_climate_forcing,
    plot_mass_balance,
    plot_mass_fractions,
    plot_objective_profile,
    plot_observed_fitted,
    plot_residuals,
    profile_cltf_parameter,
    simulate_cltf,
    weight_bulk_density,
)
from cltf import __version__ as CLTF_VERSION


ALLOWED_CASES = (
    "nsw_griffith_heavy_imazapic",
    "sa_minnipa_heavy_imazapic",
)
PARAMETER_NAMES = ("mu", "sigma", "R_top", "R_bottom", "k")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a shared CLTF reference case with the Python package.",
    )
    parser.add_argument("--case", required=True, choices=ALLOWED_CASES)
    parser.add_argument("--input-dir", default="")
    parser.add_argument("--output-dir", default="")
    arguments = parser.parse_args()
    if not arguments.input_dir:
        arguments.input_dir = str(
            REPOSITORY_DIR / "examples" / "data" / arguments.case
        )
    if not arguments.output_dir:
        arguments.output_dir = str(REPOSITORY_DIR / "reference" / arguments.case)
    return arguments


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required input file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required input file does not exist: {path}")
    return path


def repository_label(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPOSITORY_DIR))
    except ValueError:
        return str(resolved)


def read_site(case: dict[str, Any]) -> pd.Series:
    sites = pd.read_json(REPOSITORY_DIR / "examples" / "data" / "sites.json")
    selected = sites.loc[sites["site_id"].eq(case["site_id"])]
    if len(selected) != 1:
        raise ValueError(f"Shared site registry does not define one row for {case['site_id']}")
    return selected.iloc[0]


def read_inputs(input_dir: Path) -> dict[str, Any]:
    paths = {
        "case": require_file(input_dir / "case.json"),
        "observations": require_file(input_dir / "observations.csv"),
        "silo": require_file(input_dir / "silo.csv"),
        "silo_metadata": require_file(input_dir / "silo_metadata.json"),
        "bulk_density": require_file(input_dir / "bulk_density.json"),
    }
    observations = pd.read_csv(paths["observations"])
    for column in ("sample_date", "application_date"):
        observations[column] = pd.to_datetime(observations[column]).dt.normalize()
    logical_columns = (
        "is_t0",
        "is_non_detect",
        "is_zero_reported",
        "lod_substituted",
        "excluded_zero",
        "used_for_calibration",
    )
    for column in logical_columns:
        if column in observations.columns and observations[column].dtype == object:
            observations[column] = observations[column].astype(str).str.upper().map(
                {"TRUE": True, "FALSE": False}
            )

    bulk_density = parse_slga_bulk_density(paths["bulk_density"])
    bulk_density.attrs["cache_path"] = str(paths["bulk_density"])
    return {
        "paths": paths,
        "case": read_json(paths["case"]),
        "observations": observations,
        "climate": parse_silo_csv(paths["silo"]),
        "silo_metadata": read_json(paths["silo_metadata"]),
        "bulk_density": bulk_density,
    }


def build_forcing(
    climate: pd.DataFrame,
    case: dict[str, Any],
    site: pd.Series,
) -> pd.DataFrame:
    application_date = pd.Timestamp(case["application_date"])
    final_date = pd.Timestamp(case["final_date"])
    selected = climate.loc[
        climate["date"].ge(application_date) & climate["date"].le(final_date)
    ].copy()
    expected_days = int((final_date - application_date).days) + 1
    if len(selected) != expected_days:
        raise ValueError("SILO forcing does not fully cover the configured case period")
    forcing = pd.DataFrame(
        {
            "date": selected["date"].to_numpy(),
            "time_days": (selected["date"] - application_date).dt.days.astype(int),
            "jdays": selected["jdays"].astype(int).to_numpy(),
            "rain_mm": selected["rain_mm"].astype(float).to_numpy(),
            "Tmax": selected["Tmax"].astype(float).to_numpy(),
            "Tmin": selected["Tmin"].astype(float).to_numpy(),
        }
    )
    forcing["pet_mm"] = pet_from_temperature(
        forcing["jdays"],
        forcing["Tmax"],
        forcing["Tmin"],
        float(site["latitude"]),
    )
    forcing["irrigation_mm"] = float(case["irrigation_mm"])
    forcing["daily_infiltration_mm"] = daily_infiltration(
        forcing["rain_mm"],
        forcing["pet_mm"],
        forcing["irrigation_mm"],
        et_factor=float(case["et_factor"]),
    )
    forcing["cumulative_infiltration_mm"] = forcing[
        "daily_infiltration_mm"
    ].cumsum()
    return forcing


def reference_starts() -> pd.DataFrame:
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


def build_parameter_table(fit: Any) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "parameter": list(PARAMETER_NAMES),
            "estimate": [fit.parameters[name] for name in PARAMETER_NAMES],
            "lower": [fit.lower[name] for name in PARAMETER_NAMES],
            "upper": [fit.upper[name] for name in PARAMETER_NAMES],
            "bound_hit": [fit.bound_hit[name] for name in PARAMETER_NAMES],
        }
    )


def build_profiles(fit: Any) -> pd.DataFrame:
    profiles = []
    for parameter in PARAMETER_NAMES:
        span = fit.upper[parameter] - fit.lower[parameter]
        lower = max(fit.lower[parameter], fit.parameters[parameter] - 0.15 * span)
        upper = min(fit.upper[parameter], fit.parameters[parameter] + 0.15 * span)
        grid = pd.unique(
            pd.Series(
                [
                    lower,
                    (lower + fit.parameters[parameter]) / 2.0,
                    fit.parameters[parameter],
                    (fit.parameters[parameter] + upper) / 2.0,
                    upper,
                ],
                dtype=float,
            )
        )
        profiles.append(
            profile_cltf_parameter(
                fit,
                parameter=parameter,
                grid=grid,
                control={"maxit": 35},
            )
        )
    return pd.concat(profiles, ignore_index=True)


def save_csv(data: pd.DataFrame, path: Path) -> None:
    data.to_csv(path, index=False, na_rep="")


def save_plot(path: Path, figure: Any) -> None:
    figure.savefig(path, dpi=140)
    plt.close(figure)


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.DataFrame):
        return [to_jsonable(row) for row in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return to_jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def run_case(arguments: argparse.Namespace) -> None:
    input_dir = Path(arguments.input_dir).resolve()
    output_dir = Path(arguments.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    inputs = read_inputs(input_dir)
    case = inputs["case"]
    site = read_site(case)
    observations = inputs["observations"].copy()
    selected = (
        observations["site_id"].eq(case["site_id"])
        & observations["soil_group"].eq(case["soil_group"])
        & observations["herbicide"].eq(case["herbicide"])
    )
    observations = observations.loc[selected].copy()
    if observations.empty:
        raise ValueError("No observations match the configured shared case")

    application_date = pd.Timestamp(case["application_date"])
    final_date = pd.Timestamp(case["final_date"])
    if (
        observations["sample_date"].lt(application_date).any()
        or observations["sample_date"].gt(final_date).any()
    ):
        raise ValueError("Observation dates fall outside the configured case period")

    top_thickness_mm = float(case["top_depth_mm"])
    bottom_thickness_mm = float(case["bottom_depth_mm"]) - top_thickness_mm
    if top_thickness_mm <= 0 or bottom_thickness_mm <= 0:
        raise ValueError("Case depth configuration must define two positive layers")

    forcing = build_forcing(inputs["climate"], case, site)
    bulk_density = inputs["bulk_density"]
    top_density = float(
        weight_bulk_density(bulk_density, 0.0, top_thickness_mm).loc[
            0,
            "estimate_g_cm3",
        ]
    )
    bottom_density = float(
        weight_bulk_density(
            bulk_density,
            top_thickness_mm,
            top_thickness_mm + bottom_thickness_mm,
        ).loc[0, "estimate_g_cm3"]
    )
    t0_top = (
        observations["is_t0"]
        & observations["depth_top_mm"].eq(0)
        & observations["depth_bottom_mm"].eq(top_thickness_mm)
        & observations["analysis_concentration_ug_kg"].notna()
        & observations["analysis_concentration_ug_kg"].gt(0)
    )
    application_rate_g_ha = infer_application_rate_g_ha(
        observations.loc[t0_top, "analysis_concentration_ug_kg"],
        0.0,
        top_thickness_mm,
        top_density,
    )

    calibration_observations = observations.loc[
        observations["used_for_calibration"]
    ].copy()
    lower = {
        "mu": 0.05,
        "sigma": 0.10,
        "R_top": 0.10,
        "R_bottom": 0.10,
        "k": 0.0,
    }
    upper = {
        "mu": 8.0,
        "sigma": 2.50,
        "R_top": 20.0,
        "R_bottom": 30.0,
        "k": 0.05,
    }
    fit = fit_cltf(
        observations=calibration_observations,
        forcing=forcing,
        application_rate_g_ha=application_rate_g_ha,
        top_bulk_density_g_cm3=top_density,
        bottom_bulk_density_g_cm3=bottom_density,
        lower=lower,
        upper=upper,
        initial={
            "mu": 1.0,
            "sigma": 0.6,
            "R_top": 2.0,
            "R_bottom": 3.0,
            "k": 0.005,
        },
        starts=reference_starts(),
        top_thickness_mm=top_thickness_mm,
        bottom_thickness_mm=bottom_thickness_mm,
        effective_porosity=float(case["effective_porosity"]),
        method=case["convolution_method"],
        n_steps=int(case["convolution_steps"]),
        control={"maxit": 250},
    )

    simulation = simulate_cltf(
        time_days=forcing["time_days"],
        cumulative_infiltration_mm=forcing["cumulative_infiltration_mm"],
        top_layer=CLTFLayer(
            fit.parameters["mu"],
            fit.parameters["sigma"],
            fit.parameters["R_top"],
            top_thickness_mm,
        ),
        bottom_layer=CLTFLayer(
            fit.parameters["mu"],
            fit.parameters["sigma"],
            fit.parameters["R_bottom"],
            bottom_thickness_mm,
        ),
        decay_rate_day=fit.parameters["k"],
        application_rate_g_ha=application_rate_g_ha,
        top_bulk_density_g_cm3=top_density,
        bottom_bulk_density_g_cm3=bottom_density,
        effective_porosity=float(case["effective_porosity"]),
        method=case["convolution_method"],
        n_steps=int(case["convolution_steps"]),
    )
    predictions = pd.concat(
        [forcing.loc[:, ["date"]].reset_index(drop=True), simulation],
        axis=1,
    )
    parameter_table = build_parameter_table(fit)
    fit_diagnostics = fit.all_starts.copy()
    fit_diagnostics["selected"] = (
        fit_diagnostics["start_index"].eq(fit.start_index)
    )
    fit_diagnostics["start_transport_scale_top"] = (
        fit_diagnostics["start_mu"] * fit_diagnostics["start_R_top"]
    )
    fit_diagnostics["start_transport_scale_bottom"] = (
        fit_diagnostics["start_mu"] * fit_diagnostics["start_R_bottom"]
    )
    fit_diagnostics["fitted_transport_scale_top"] = (
        fit_diagnostics["fitted_mu"] * fit_diagnostics["fitted_R_top"]
    )
    fit_diagnostics["fitted_transport_scale_bottom"] = (
        fit_diagnostics["fitted_mu"] * fit_diagnostics["fitted_R_bottom"]
    )
    profiles = build_profiles(fit)

    output_paths = {
        "observations": output_dir / "observations_prepared.csv",
        "forcing": output_dir / "climate_forcing.csv",
        "bulk_density": output_dir / "bulk_density.csv",
        "predictions": output_dir / "predictions.csv",
        "parameters": output_dir / "fit_parameters.csv",
        "diagnostics": output_dir / "fit_diagnostics.csv",
        "profiles": output_dir / "objective_profiles.csv",
        "metadata": output_dir / "metadata.json",
    }
    save_csv(observations, output_paths["observations"])
    save_csv(forcing, output_paths["forcing"])
    save_csv(bulk_density, output_paths["bulk_density"])
    save_csv(predictions, output_paths["predictions"])
    save_csv(parameter_table, output_paths["parameters"])
    save_csv(fit_diagnostics, output_paths["diagnostics"])
    save_csv(profiles, output_paths["profiles"])

    save_plot(output_dir / "plot_bulk_density.png", plot_bulk_density(bulk_density))
    save_plot(output_dir / "plot_climate.png", plot_climate_forcing(forcing))
    save_plot(output_dir / "plot_mass_balance.png", plot_mass_balance(simulation))
    save_plot(output_dir / "plot_mass_fractions.png", plot_mass_fractions(simulation))
    save_plot(output_dir / "plot_observed_fitted.png", plot_observed_fitted(fit.predictions))
    save_plot(output_dir / "plot_profiles.png", plot_objective_profile(profiles))
    save_plot(output_dir / "plot_residuals.png", plot_residuals(fit.predictions))

    input_files = inputs["paths"]
    checksums = {
        path.name: md5sum(path)
        for path in input_files.values()
    }
    metadata = {
        "reference_case": " / ".join(
            [case["site_id"], case["soil_group"], case["herbicide"]]
        ),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "software": {
            "package_version": CLTF_VERSION,
            "python_version": sys.version,
        },
        "source_input_dir": repository_label(input_dir),
        "concentration": {
            "unit": case["concentration_unit"],
            "unit_status": case["unit_status"],
        },
        "application_rate": {
            "value_g_ha": application_rate_g_ha,
            "source": (
                "inferred from the geometric mean of positive top-layer "
                "T0 replicates"
            ),
            "t0_rows": int(t0_top.sum()),
        },
        "observations": {
            "total_rows": int(len(observations)),
            "calibration_rows": int(observations["used_for_calibration"].sum()),
            "t0_rows_excluded": int(observations["is_t0"].sum()),
            "zero_rows_excluded": int(observations["excluded_zero"].sum()),
            "non_detect_substitutions": int(observations["lod_substituted"].sum()),
        },
        "silo": {
            "source": inputs["silo_metadata"]["source"],
            "request_latitude": inputs["silo_metadata"]["request_latitude"],
            "request_longitude": inputs["silo_metadata"]["request_longitude"],
            "returned_latitude": inputs["silo_metadata"]["grid_latitude"],
            "returned_longitude": inputs["silo_metadata"]["grid_longitude"],
            "cache_file": input_files["silo"].name,
        },
        "slga": {
            "product": "SLGA Bulk Density (whole earth)",
            "product_version": "v2",
            "latitude": float(site["latitude"]),
            "longitude": float(site["longitude"]),
            "cache_file": Path(bulk_density.attrs["cache_path"]).name,
            "source_status": bulk_density["source"].drop_duplicates().tolist(),
            "depth_bands_mm": bulk_density.loc[
                :,
                ["depth_top_mm", "depth_bottom_mm"],
            ],
            "top_layer_g_cm3": top_density,
            "bottom_layer_g_cm3": bottom_density,
        },
        "model": {
            "target_quantity": "layer-average resident concentration",
            "top_thickness_mm": top_thickness_mm,
            "bottom_thickness_mm": bottom_thickness_mm,
            "effective_porosity": float(case["effective_porosity"]),
            "degradation_clock": "total elapsed time",
            "water_balance": "max(rain + irrigation - PET, 0) accumulated daily",
            "et_factor": float(case["et_factor"]),
            "irrigation_mm": float(case["irrigation_mm"]),
            "convolution_method": case["convolution_method"],
            "convolution_steps": int(case["convolution_steps"]),
        },
        "calibration": {
            "objective": "replicate-level root mean squared log residual",
            "objective_value": fit.objective,
            "convergence": fit.convergence,
            "message": fit.message,
            "selected_start": fit.start_index,
            "bounds": parameter_table.loc[:, ["parameter", "lower", "upper"]],
            "starts": pd.DataFrame(fit.starts, columns=PARAMETER_NAMES),
            "bound_hits": fit.bound_hit,
            "transport_scales": fit.transport_scales,
            "identifiability_note": fit.identifiability_note,
        },
        "input_checksums": checksums,
    }
    output_paths["metadata"].write_text(
        json.dumps(to_jsonable(metadata), indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {case['site_id']} {case['soil_group']}/{case['herbicide']} "
        f"reference outputs to {output_dir}"
    )
    print(f"Objective: {fit.objective:.8g}")


if __name__ == "__main__":
    run_case(parse_arguments())
