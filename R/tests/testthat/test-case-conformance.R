#!/usr/bin/env Rscript
# Script: test-case-conformance.R
# Objective: Verify committed R case references are forward-model reproducible.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Committed NSW and SA reference artifacts.
# Outputs: Testthat assertions for deterministic forward reproducibility.
# Usage: Loaded by testthat::test_local("R", filter = "case-conformance").
# Dependencies: testthat, cltf, jsonlite

case_reference_path <- function(case_id, filename) {
  path <- testthat::test_path("..", "..", "..", "reference", case_id, filename)
  if (!file.exists(path)) {
    skip("Case reference artifacts are available only from a source checkout.")
  }
  path
}

case_ids <- c(
  "nsw_griffith_heavy_imazapic",
  "sa_minnipa_heavy_imazapic"
)

test_that("committed case references reproduce forward predictions", {
  for (case_id in case_ids) {
    forcing <- utils::read.csv(case_reference_path(case_id, "climate_forcing.csv"))
    bulk_density <- utils::read.csv(case_reference_path(case_id, "bulk_density.csv"))
    predictions <- utils::read.csv(case_reference_path(case_id, "predictions.csv"))
    parameters <- utils::read.csv(case_reference_path(case_id, "fit_parameters.csv"))
    metadata <- jsonlite::fromJSON(case_reference_path(case_id, "metadata.json"))
    parameter_values <- stats::setNames(
      parameters$estimate,
      parameters$parameter
    )
    top_thickness <- metadata$model$top_thickness_mm
    bottom_thickness <- metadata$model$bottom_thickness_mm
    top_density <- weight_bulk_density(
      bulk_density,
      0,
      top_thickness
    )$estimate_g_cm3
    bottom_density <- weight_bulk_density(
      bulk_density,
      top_thickness,
      top_thickness + bottom_thickness
    )$estimate_g_cm3

    rerun <- simulate_cltf(
      time_days                   = forcing$time_days,
      cumulative_infiltration_mm = forcing$cumulative_infiltration_mm,
      top_layer                  = cltf_layer(
        parameter_values["mu"],
        parameter_values["sigma"],
        parameter_values["R_top"],
        top_thickness
      ),
      bottom_layer               = cltf_layer(
        parameter_values["mu"],
        parameter_values["sigma"],
        parameter_values["R_bottom"],
        bottom_thickness
      ),
      decay_rate_day             = parameter_values["k"],
      application_rate_g_ha      = metadata$application_rate$value_g_ha,
      top_bulk_density_g_cm3     = top_density,
      bottom_bulk_density_g_cm3  = bottom_density,
      effective_porosity         = metadata$model$effective_porosity,
      method                     = metadata$model$convolution_method,
      n_steps                    = metadata$model$convolution_steps
    )

    expect_equal(rerun$mass_top, predictions$mass_top, tolerance = 1e-8)
    expect_equal(rerun$mass_bottom, predictions$mass_bottom, tolerance = 1e-8)
    expect_equal(rerun$mass_below, predictions$mass_below, tolerance = 1e-8)
    expect_equal(rerun$mass_degraded, predictions$mass_degraded, tolerance = 1e-8)
    expect_equal(
      rerun$concentration_top_ug_kg,
      predictions$concentration_top_ug_kg,
      tolerance = 1e-8
    )
    expect_equal(
      rerun$concentration_bottom_ug_kg,
      predictions$concentration_bottom_ug_kg,
      tolerance = 1e-8
    )
  }
})
