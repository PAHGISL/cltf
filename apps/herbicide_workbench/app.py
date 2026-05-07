#!/usr/bin/env python3
"""
Script: app.py
Objective: Launch a Streamlit research workbench for uploading herbicide model CSVs, running PyCLT simulations, fitting selected cases, and exporting outputs.
Author: Codex
Created: 2026-05-07
Last updated: 2026-05-07
Inputs: Uploaded climate, observation, and optional site configuration CSV files.
Outputs: Interactive plots and downloadable CSV/JSON run artifacts.
Usage: streamlit run apps/herbicide_workbench/app.py
Dependencies: streamlit, pandas, matplotlib, scipy, PyCLT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workbench import APP_NAME, APP_VERSION
from workbench.adapters import PyCLTAdapter
from workbench.contracts import CaseSelection
from workbench.exports import build_export_artifacts
from workbench.plots import plot_forcing, plot_observed_vs_model
from workbench.validation import (
    ValidationError,
    build_input_bundle,
    list_cases,
    prepare_climate,
    prepare_observations,
    prepare_site_config,
)


def read_csv_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    return pd.read_csv(uploaded_file)


def case_label(case: CaseSelection) -> str:
    return f"{case.site_id} / {case.soil_group} / {case.herbicide}"


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")
    st.title(APP_NAME)

    adapter = PyCLTAdapter()
    specs = adapter.parameter_specs()
    defaults = adapter.default_parameters()

    with st.sidebar:
        st.header("Inputs")
        climate_upload = st.file_uploader("Climate CSV", type=["csv"])
        observations_upload = st.file_uploader("Observations CSV", type=["csv"])
        site_upload = st.file_uploader("Site config CSV", type=["csv"])

        st.header("Fallback Site Values")
        fallback_site = st.text_input("site_id", value="site")
        fallback_soil = st.text_input("soil_group", value="soil")
        fallback_lat = st.number_input("representative_lat", value=-32.85, format="%.6f")
        fallback_lon = st.number_input("representative_lon", value=135.15, format="%.6f")
        fallback_app_date = st.date_input("application_date")
        fallback_top_depth = st.number_input("top_thickness_mm", value=100.0, min_value=1.0)
        fallback_ref_depth = st.number_input("reference_depth_mm", value=100.0, min_value=1.0)
        fallback_bottom_depth = st.number_input("bottom_depth_mm", value=300.0, min_value=1.0)

        st.header("Parameters")
        parameters: dict[str, float] = {}
        for spec in specs:
            parameters[spec.name] = float(
                st.number_input(
                    spec.label,
                    min_value=float(spec.minimum),
                    max_value=float(spec.maximum),
                    value=float(defaults[spec.name]),
                    step=float(spec.step),
                    help=spec.description,
                )
            )
        run_clicked = st.button("Run simulation", type="primary")
        fit_clicked = st.button("Fit selected case")

    climate_raw = read_csv_upload(climate_upload)
    observations_raw = read_csv_upload(observations_upload)
    site_raw = read_csv_upload(site_upload)

    if climate_raw is None or observations_raw is None:
        st.info("Upload at least a climate CSV and observations CSV to start.")
        return

    try:
        site_config = prepare_site_config(site_raw)
        if site_config.empty:
            site_config = pd.DataFrame(
                {
                    "site_id": [fallback_site],
                    "soil_group": [fallback_soil],
                    "representative_lat": [fallback_lat],
                    "representative_lon": [fallback_lon],
                    "application_date": [pd.Timestamp(fallback_app_date)],
                    "top_thickness_mm": [fallback_top_depth],
                    "reference_depth_mm": [fallback_ref_depth],
                    "bottom_depth_mm": [fallback_bottom_depth],
                }
            )
        latitude = float(site_config["representative_lat"].iloc[0])
        climate, climate_warnings = prepare_climate(climate_raw, latitude=latitude, et_factor=parameters["et_factor"])
        observations, observation_warnings = prepare_observations(observations_raw, site_config)
        warnings = climate_warnings + observation_warnings
    except ValidationError as exc:
        st.error(str(exc))
        return

    cases = list_cases(observations)
    if not cases:
        st.error("No site / soil / herbicide cases found in observations.")
        return

    case_labels = [case_label(case) for case in cases]
    selected_label = st.selectbox("Selected case", case_labels)
    selected_case = cases[case_labels.index(selected_label)]

    try:
        bundle = build_input_bundle(climate, observations, site_config, selected_case)
    except ValidationError as exc:
        st.error(str(exc))
        return

    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("Inputs validated.")

    with st.expander("Prepared input previews", expanded=False):
        st.subheader("Climate")
        st.dataframe(bundle.climate.head(50), use_container_width=True)
        st.subheader("Observations")
        st.dataframe(bundle.observations.head(50), use_container_width=True)
        st.subheader("Site config")
        st.dataframe(bundle.site_config, use_container_width=True)

    st.subheader("Climate forcing")
    st.pyplot(plot_forcing(bundle.climate), clear_figure=True)

    if run_clicked or fit_clicked:
        manual_result = adapter.simulate(bundle, parameters)
        combined_predictions = manual_result.predictions.copy()
        active_result = manual_result
        active_parameters = dict(parameters)

        if fit_clicked:
            fit = adapter.fit(bundle, parameters)
            active_result = fit.result
            active_parameters = fit.parameters
            combined_predictions = pd.concat([manual_result.predictions, fit.result.predictions], ignore_index=True)
            st.subheader("Fit result")
            st.write(
                {
                    "success": fit.success,
                    "objective_rmse_log1p": fit.objective_value,
                    "message": fit.message,
                }
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "parameter": name,
                            "value": value,
                            "bound_hit": fit.bound_hits.get(name, False),
                        }
                        for name, value in fit.parameters.items()
                    ]
                ),
                use_container_width=True,
            )

        st.subheader("Observed vs model")
        top_depth = float(bundle.site_config["top_thickness_mm"].iloc[0])
        st.pyplot(plot_observed_vs_model(bundle.observations, combined_predictions, top_depth), clear_figure=True)

        st.subheader("Model output")
        st.dataframe(combined_predictions, use_container_width=True)

        artifacts = build_export_artifacts(
            result=active_result,
            observations=bundle.observations,
            site_config=bundle.site_config,
            parameters=active_parameters,
            case=selected_case,
            app_version=APP_VERSION,
        )
        st.subheader("Downloads")
        for filename, payload in artifacts.items():
            mime = "application/json" if filename.endswith(".json") else "text/csv"
            st.download_button(filename, payload, file_name=filename, mime=mime)


if __name__ == "__main__":
    main()
