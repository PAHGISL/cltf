#!/usr/bin/env Rscript
# Script: test-sa-regression.R
# Objective: Lock the committed SA Minnipa Heavy/Imazapic reference artifacts.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Committed reference CSV and JSON outputs.
# Outputs: Structural, mass-balance, parameter-bound, and forward-model assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "sa-regression").
# Dependencies: testthat, rclt, jsonlite

sa_reference_path <- function(filename) {
  path <- testthat::test_path(
    "..",
    "..",
    "reference",
    "sa_minnipa_heavy_imazapic",
    filename
  )
  if (!file.exists(path)) {
    skip(
      paste(
        "Full reference artifacts are verified from the source tree and",
        "are not included in built package tarballs."
      )
    )
  }
  path
}

test_that("SA reference artifacts have stable schemas and dimensions", {
  observations <- utils::read.csv(sa_reference_path("observations_prepared.csv"))
  forcing <- utils::read.csv(sa_reference_path("climate_forcing.csv"))
  bulk_density <- utils::read.csv(sa_reference_path("bulk_density.csv"))
  predictions <- utils::read.csv(sa_reference_path("predictions.csv"))
  parameters <- utils::read.csv(sa_reference_path("fit_parameters.csv"))

  expect_equal(nrow(observations), 31)
  expect_equal(nrow(forcing), 139)
  expect_equal(nrow(bulk_density), 3)
  expect_equal(nrow(predictions), 139)
  expect_equal(nrow(parameters), 5)
  expect_true(all(c(
    "analysis_concentration_ug_kg",
    "used_for_calibration"
  ) %in% names(observations)))
  expect_true(all(c(
    "pet_mm",
    "daily_infiltration_mm",
    "cumulative_infiltration_mm"
  ) %in% names(forcing)))
  expect_true(all(c(
    "mass_top",
    "mass_bottom",
    "mass_below",
    "mass_degraded",
    "concentration_top_ug_kg",
    "concentration_bottom_ug_kg"
  ) %in% names(predictions)))
})

test_that("SA reference conserves mass and respects parameter bounds", {
  predictions <- utils::read.csv(sa_reference_path("predictions.csv"))
  parameters <- utils::read.csv(sa_reference_path("fit_parameters.csv"))
  total <- rowSums(predictions[c(
    "mass_top",
    "mass_bottom",
    "mass_below",
    "mass_degraded"
  )])

  expect_equal(total, rep(1, length(total)), tolerance = 1e-8)
  expect_true(all(is.finite(predictions$concentration_top_ug_kg)))
  expect_true(all(is.finite(predictions$concentration_bottom_ug_kg)))
  expect_true(all(predictions$concentration_top_ug_kg >= 0))
  expect_true(all(predictions$concentration_bottom_ug_kg >= 0))
  expect_true(all(parameters$estimate >= parameters$lower))
  expect_true(all(parameters$estimate <= parameters$upper))
})

test_that("SA cached inputs reproduce the committed forward predictions", {
  forcing <- utils::read.csv(sa_reference_path("climate_forcing.csv"))
  bulk_density <- utils::read.csv(sa_reference_path("bulk_density.csv"))
  predictions <- utils::read.csv(sa_reference_path("predictions.csv"))
  parameters <- utils::read.csv(sa_reference_path("fit_parameters.csv"))
  metadata <- jsonlite::fromJSON(sa_reference_path("metadata.json"))
  parameter_values <- stats::setNames(
    parameters$estimate,
    parameters$parameter
  )
  top_density <- weight_bulk_density(bulk_density, 0, 100)$estimate_g_cm3
  bottom_density <- weight_bulk_density(bulk_density, 100, 300)$estimate_g_cm3

  rerun <- simulate_rclt(
    time_days                   = forcing$time_days,
    cumulative_infiltration_mm = forcing$cumulative_infiltration_mm,
    top_layer                  = cltf_layer(
      parameter_values["mu"],
      parameter_values["sigma"],
      parameter_values["R_top"],
      100
    ),
    bottom_layer               = cltf_layer(
      parameter_values["mu"],
      parameter_values["sigma"],
      parameter_values["R_bottom"],
      200
    ),
    decay_rate_day             = parameter_values["k"],
    application_rate_g_ha      = metadata$application_rate$value_g_ha,
    top_bulk_density_g_cm3     = top_density,
    bottom_bulk_density_g_cm3  = bottom_density,
    effective_porosity         = metadata$model$effective_porosity,
    method                      = metadata$model$convolution_method,
    n_steps                     = metadata$model$convolution_steps
  )

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
})
