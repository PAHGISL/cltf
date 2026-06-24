#!/usr/bin/env python3
"""
Script: test_package.py
Objective: Verify Python CLTF package metadata and public imports.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Installed editable Python package.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_package.py -q
Dependencies: pytest, cltf
"""

import cltf


def test_package_version() -> None:
    assert cltf.__version__ == "0.1.0"


def test_complete_public_api_is_exported() -> None:
    expected = {
        "CLTFFit",
        "CLTFLayer",
        "apply_elapsed_degradation",
        "cltf_cdf",
        "cltf_layer_probabilities",
        "cltf_objective",
        "cltf_pdf",
        "cltf_two_layer_cdf",
        "cumulative_infiltration",
        "daily_infiltration",
        "depth_interval_mm",
        "fetch_silo_point",
        "fetch_slga_bulk_density",
        "first_passage_time",
        "fit_cltf",
        "geometric_concentration",
        "infer_application_rate_g_ha",
        "parse_silo_csv",
        "parse_slga_bulk_density",
        "pet_from_temperature",
        "plot_bulk_density",
        "plot_climate_forcing",
        "plot_mass_balance",
        "plot_mass_fractions",
        "plot_objective_profile",
        "plot_observed_fitted",
        "plot_residuals",
        "prepare_non_detects",
        "profile_cltf_parameter",
        "read_herbicide_workbook",
        "resident_concentration_ug_kg",
        "round_silo_coordinate",
        "simulate_cltf",
        "soil_mass_kg_ha",
        "weight_bulk_density",
    }
    assert set(cltf.__all__) == expected
    assert all(hasattr(cltf, name) for name in expected)
