#!/usr/bin/env python3
"""
Script: app.py
Objective: Launch a Streamlit CLTF workbench for herbicide residue assessment.
Author: Yi Yu
Created: 2026-05-07
Last updated: 2026-06-24
Inputs: Observation CSV uploads, shared site registry, cached/API climate, and cached/API soil.
Outputs: Interactive maps, CLTF diagnostics, assessment summaries, and downloads.
Usage: streamlit run apps/herbicide_workbench/app.py
Dependencies: os, pathlib, pandas, streamlit, workbench
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workbench import APP_NAME, APP_VERSION
from workbench.assessment import (
    assessment_date_from_preset,
    default_assessment_date,
    validate_assessment_date,
)
from workbench.contracts import CaseSelection, PreparedInputs
from workbench.data_services import prepare_external_inputs
from workbench.exports import build_export_artifacts
from workbench.maps import build_site_map
from workbench.model_service import (
    default_parameters,
    fit_case,
    infer_application_rate_from_observations,
)
from workbench.plots import (
    plot_bulk_density,
    plot_climate_forcing,
    plot_mass_balance,
    plot_mass_fractions,
    plot_objective_profiles,
    plot_observed_fitted,
    plot_residuals,
)
from workbench.site_registry import (
    available_herbicides,
    available_soils,
    case_input_dir,
    default_case,
    get_site,
    load_site_registry,
)
from workbench.validation import ValidationError, prepare_uploaded_observations


def _site_display(site: dict[str, object]) -> str:
    return str(site.get("display_name", site["site_id"]))


def _read_observations(
    uploaded_file: object | None,
    case: CaseSelection,
) -> pd.DataFrame:
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    return pd.read_csv(case_input_dir(case) / "observations.csv")


def _filter_case_observations(
    observations: pd.DataFrame,
    case: CaseSelection,
) -> pd.DataFrame:
    selected = observations.loc[
        observations["site_id"].astype(str).eq(case.site_id)
        & observations["soil_group"].astype(str).eq(case.soil_group)
        & observations["herbicide"].astype(str).eq(case.herbicide)
    ].copy()
    if selected.empty:
        raise ValidationError(
            "No prepared observations match the selected site, soil, and herbicide."
        )
    return selected.reset_index(drop=True)


def _assessment_from_preset(
    preset: str,
    application_date: pd.Timestamp,
    final_date: pd.Timestamp,
    fallback: pd.Timestamp,
) -> pd.Timestamp:
    if preset == "Custom":
        return fallback
    days = int(preset.split()[0])
    try:
        return assessment_date_from_preset(application_date, days, final_date)
    except ValueError:
        return fallback


def _prepared_inputs(
    case: CaseSelection,
    site: dict[str, object],
    observations: pd.DataFrame,
    external_inputs,
    application_rate_g_ha: float,
    top_bulk_density_g_cm3: float,
    bottom_bulk_density_g_cm3: float,
) -> PreparedInputs:
    application_date = pd.Timestamp(
        external_inputs.metadata["application_date"]
    ).normalize()
    return PreparedInputs(
        case=case,
        site=site,
        observations=observations,
        forcing=external_inputs.forcing,
        bulk_density=external_inputs.bulk_density,
        application_date=application_date,
        application_rate_g_ha=application_rate_g_ha,
        top_bulk_density_g_cm3=top_bulk_density_g_cm3,
        bottom_bulk_density_g_cm3=bottom_bulk_density_g_cm3,
    )


def _show_provenance(
    external_inputs,
    application_rate_g_ha: float,
    application_rate_source: str,
) -> None:
    st.subheader("Input provenance")
    columns = st.columns(4)
    columns[0].metric("Climate", str(external_inputs.metadata["climate_source"]))
    columns[1].metric("Bulk density", str(external_inputs.metadata["soil_source"]))
    columns[2].metric("Application rate", f"{application_rate_g_ha:.2f} g/ha")
    columns[3].metric("Rate source", application_rate_source)
    for warning in external_inputs.warnings:
        st.warning(warning)


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide")
    st.title(APP_NAME)
    st.caption(
        "Historical CLTF analysis for layer-average resident herbicide "
        "concentration. Forecasting from climatology is a future extension."
    )

    registry = load_site_registry()
    default = default_case(registry)
    sites_by_display = {
        _site_display(site): str(site["site_id"])
        for site in registry
    }
    default_site = _site_display(get_site(default.site_id))

    st.subheader("Case selection")
    case_columns = st.columns(3)
    site_display = case_columns[0].selectbox(
        "Site",
        list(sites_by_display),
        index=list(sites_by_display).index(default_site),
    )
    site_id = sites_by_display[site_display]
    soils = available_soils(site_id)
    soil_group = case_columns[1].selectbox(
        "Soil group",
        soils,
        index=soils.index(default.soil_group) if default.soil_group in soils else 0,
    )
    herbicides = available_herbicides(site_id, soil_group)
    herbicide = case_columns[2].selectbox(
        "Herbicide",
        herbicides,
        index=(
            herbicides.index(default.herbicide)
            if default.herbicide in herbicides
            else 0
        ),
    )
    case = CaseSelection(site_id, soil_group, herbicide)
    site = get_site(case.site_id)

    with st.sidebar:
        st.header("Observation data")
        source_mode = st.radio(
            "Observation source",
            ["Bundled showcase", "Upload observation CSV"],
        )
        upload = (
            st.file_uploader("Observation CSV", type=["csv"])
            if source_mode == "Upload observation CSV"
            else None
        )

        st.header("API refresh")
        refresh_climate = st.checkbox("Refresh SILO climate", value=False)
        refresh_soil = st.checkbox("Refresh SLGA bulk density", value=False)

    st.subheader("Selected site")
    st.pydeck_chart(
        build_site_map(site, mapbox_token=os.getenv("MAPBOX_API_KEY", "")),
        width="stretch",
    )

    try:
        raw_observations = _read_observations(upload, case)
        observations = prepare_uploaded_observations(
            raw_observations,
            site,
            soil_group=case.soil_group,
            herbicide=case.herbicide,
        )
        observations = _filter_case_observations(observations, case)
        external_inputs = prepare_external_inputs(
            case,
            environment=os.environ,
            refresh_climate=refresh_climate,
            refresh_soil=refresh_soil,
        )
        inferred_rate = infer_application_rate_from_observations(
            observations,
            float(site["top_depth_mm"]),
            external_inputs.top_bulk_density_g_cm3,
        )
    except (ValidationError, ValueError, FileNotFoundError, KeyError) as error:
        st.error(str(error))
        return

    application_date = pd.Timestamp(
        external_inputs.metadata["application_date"]
    ).normalize()
    final_date = pd.Timestamp(external_inputs.metadata["final_date"]).normalize()
    default_assessment = default_assessment_date(
        application_date,
        external_inputs.forcing["date"],
    )

    st.subheader("Residue assessment")
    preset = st.selectbox(
        "Assessment preset",
        ["90 days beyond application", "60 days beyond application", "120 days beyond application", "Custom"],
    )
    preset_date = _assessment_from_preset(
        preset,
        application_date,
        final_date,
        default_assessment,
    )
    assessment_date = pd.Timestamp(
        st.date_input(
            "Residue assessment date",
            value=preset_date.date(),
            min_value=application_date.date(),
            max_value=final_date.date(),
            help="Limited to the period covered by observed SILO climate.",
        )
    ).normalize()
    try:
        validate_assessment_date(assessment_date, application_date, final_date)
    except ValueError as error:
        st.error(str(error))
        return
    assessment_day = int((assessment_date - application_date).days)

    with st.expander("Advanced overrides", expanded=False):
        application_rate = st.number_input(
            "Application rate (g/ha)",
            value=float(inferred_rate),
            min_value=0.0,
            format="%.6f",
            help=(
                "Default is inferred from positive top-layer T0 "
                "resident concentrations."
            ),
        )
        top_bulk_density = st.number_input(
            "Top-layer bulk density (g/cm³)",
            value=float(external_inputs.top_bulk_density_g_cm3),
            min_value=0.01,
            format="%.4f",
        )
        bottom_bulk_density = st.number_input(
            "Bottom-layer bulk density (g/cm³)",
            value=float(external_inputs.bottom_bulk_density_g_cm3),
            min_value=0.01,
            format="%.4f",
        )
        effective_porosity = st.number_input(
            "Effective porosity concentration scale",
            value=0.2,
            min_value=0.001,
            format="%.4f",
            help="Porosity scales concentration only; transport is unchanged.",
        )

    rate_source = (
        "inferred_top_layer_t0"
        if abs(float(application_rate) - float(inferred_rate)) < 1e-12
        else "advanced_override"
    )
    _show_provenance(external_inputs, float(application_rate), rate_source)

    with st.expander("Prepared input previews", expanded=False):
        st.subheader("Observations")
        st.dataframe(observations, width="stretch")
        st.subheader("Climate forcing")
        st.dataframe(external_inputs.forcing, width="stretch")
        st.subheader("Bulk density")
        st.dataframe(external_inputs.bulk_density, width="stretch")

    st.subheader("Cached forcing and soil diagnostics")
    left, right = st.columns(2)
    left.pyplot(
        plot_climate_forcing(
            external_inputs.forcing,
            assessment_date=assessment_date,
        ),
        clear_figure=True,
    )
    right.pyplot(plot_bulk_density(external_inputs.bulk_density), clear_figure=True)

    run_clicked = st.button("Run CLTF fit and assessment", type="primary")
    if not run_clicked:
        st.info("Run the CLTF fit to generate predictions, diagnostics, and downloads.")
        return

    prepared = _prepared_inputs(
        case,
        site,
        observations,
        external_inputs,
        float(application_rate),
        float(top_bulk_density),
        float(bottom_bulk_density),
    )
    with st.spinner("Fitting the Python CLTF model..."):
        result = fit_case(
            prepared,
            default_parameters(effective_porosity=float(effective_porosity)),
            assessment_date=assessment_date,
            application_rate_g_ha=float(application_rate),
        )
        result.warnings.extend(external_inputs.warnings)
        result.metadata.update(external_inputs.metadata)
        result.metadata["application_rate_source"] = rate_source
        result.metadata["application_rate_g_ha"] = float(application_rate)

    st.subheader("Assessment summary")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Assessment day", result.assessment.time_days)
    summary_columns[1].metric(
        "Top concentration",
        f"{result.assessment.concentration_top_ug_kg:.4g} µg/kg",
    )
    summary_columns[2].metric(
        "Bottom concentration",
        f"{result.assessment.concentration_bottom_ug_kg:.4g} µg/kg",
    )
    summary_columns[3].metric(
        "Resident profile fraction",
        f"{result.assessment.resident_profile_fraction:.4g}",
    )

    if result.fit is not None:
        st.subheader("Fit diagnostics")
        st.write(
            {
                "objective": result.fit.objective,
                "convergence": result.fit.convergence,
                "message": result.fit.message,
                "identifiability_note": result.fit.identifiability_note,
            }
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "parameter": list(result.parameters),
                    "estimate": list(result.parameters.values()),
                    "bound_hit": [
                        result.fit.bound_hit[name]
                        for name in result.parameters
                    ],
                }
            ),
            width="stretch",
        )

    st.subheader("CLTF diagnostic plots")
    st.pyplot(
        plot_observed_fitted(result.fit.predictions, assessment_day=assessment_day),
        clear_figure=True,
    )
    left, right = st.columns(2)
    left.pyplot(
        plot_mass_fractions(result.predictions, assessment_day=assessment_day),
        clear_figure=True,
    )
    right.pyplot(
        plot_mass_balance(result.predictions, assessment_day=assessment_day),
        clear_figure=True,
    )
    left, right = st.columns(2)
    left.pyplot(plot_residuals(result.fit.predictions), clear_figure=True)
    profiles = result.metadata.get("objective_profiles")
    if isinstance(profiles, pd.DataFrame) and not profiles.empty:
        right.pyplot(plot_objective_profiles(profiles), clear_figure=True)

    st.subheader("Predictions")
    st.dataframe(result.predictions, width="stretch")

    artifacts = build_export_artifacts(result, prepared, APP_VERSION)
    st.subheader("Downloads")
    for filename, payload in artifacts.items():
        mime = "application/json" if filename.endswith(".json") else "text/csv"
        st.download_button(
            filename,
            payload,
            file_name=filename,
            mime=mime,
        )


if __name__ == "__main__":
    main()
