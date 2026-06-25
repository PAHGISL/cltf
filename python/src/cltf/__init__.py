#!/usr/bin/env python3
"""
Script: __init__.py
Objective: Expose the public interface for the Python CLTF implementation.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Python CLTF package modules.
Outputs: Public package metadata and exports.
Usage: import cltf
Dependencies: cltf package modules
"""

from .calibration import (
    CLTFFit,
    cltf_objective,
    cltf_profile_objective,
    fit_cltf,
    fit_cltf_profile,
    profile_cltf_parameter,
    profile_cltf_profile_parameter,
)
from .climate import pet_from_temperature
from .concentration import (
    apply_elapsed_degradation,
    resident_concentration_ug_kg,
    soil_mass_kg_ha,
)
from .observations import (
    depth_interval_mm,
    geometric_concentration,
    infer_application_rate_g_ha,
    prepare_non_detects,
    read_herbicide_workbook,
)
from .plotting import (
    plot_bulk_density,
    plot_climate_forcing,
    plot_mass_balance,
    plot_mass_fractions,
    plot_objective_profile,
    plot_observed_fitted,
    plot_residuals,
)
from .silo import fetch_silo_point, parse_silo_csv, round_silo_coordinate
from .simulation import simulate_cltf, simulate_cltf_intervals, simulate_cltf_profile
from .slga import (
    fetch_slga_bulk_density,
    parse_slga_bulk_density,
    weight_bulk_density,
)
from .transport import (
    CLTFLayer,
    cltf_cdf,
    cltf_depth_cdf,
    cltf_interval_probabilities,
    cltf_layer_probabilities,
    cltf_pdf,
    cltf_two_layer_cdf,
)
from .water_balance import (
    cumulative_infiltration,
    daily_infiltration,
    first_passage_time,
)

__version__ = "0.1.0"

__all__ = [
    "CLTFFit",
    "CLTFLayer",
    "apply_elapsed_degradation",
    "cltf_cdf",
    "cltf_depth_cdf",
    "cltf_interval_probabilities",
    "cltf_layer_probabilities",
    "cltf_objective",
    "cltf_pdf",
    "cltf_profile_objective",
    "cltf_two_layer_cdf",
    "cumulative_infiltration",
    "daily_infiltration",
    "depth_interval_mm",
    "fetch_silo_point",
    "fetch_slga_bulk_density",
    "first_passage_time",
    "fit_cltf",
    "fit_cltf_profile",
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
    "profile_cltf_profile_parameter",
    "read_herbicide_workbook",
    "resident_concentration_ug_kg",
    "round_silo_coordinate",
    "simulate_cltf",
    "simulate_cltf_intervals",
    "simulate_cltf_profile",
    "soil_mass_kg_ha",
    "weight_bulk_density",
]
