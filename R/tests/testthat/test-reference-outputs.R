#!/usr/bin/env Rscript
# Script: test-reference-outputs.R
# Objective: Verify committed NSW and SA R reference output artifacts.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Committed reference CSV and JSON outputs.
# Outputs: Structural, mass-balance, and parameter-bound assertions.
# Usage: Loaded by testthat::test_local("R", filter = "reference-outputs").
# Dependencies: testthat, jsonlite

reference_output_path <- function(case_id, filename) {
  root <- testthat::test_path("..", "..", "..", "reference")
  if (!dir.exists(root)) {
    skip("Reference artifacts are verified only from a source checkout.")
  }
  file.path(root, case_id, filename)
}

expect_reference_file <- function(case_id, filename) {
  path <- reference_output_path(case_id, filename)
  expect_true(file.exists(path), info = paste("missing", case_id, filename))
  path
}

shared_reference_cases <- data.frame(
  case_id = c(
    "nsw_griffith_heavy_imazapic",
    "sa_minnipa_heavy_imazapic"
  ),
  observation_rows = c(30L, 31L),
  forcing_rows     = c(147L, 139L),
  stringsAsFactors = FALSE
)

test_that("reference outputs have stable schemas and dimensions", {
  expected_files <- c(
    "bulk_density.csv",
    "climate_forcing.csv",
    "fit_diagnostics.csv",
    "fit_parameters.csv",
    "metadata.json",
    "objective_profiles.csv",
    "observations_prepared.csv",
    "predictions.csv"
  )

  for (case_index in seq_len(nrow(shared_reference_cases))) {
    case <- shared_reference_cases[case_index, ]
    paths <- vapply(
      expected_files,
      function(filename) expect_reference_file(case$case_id, filename),
      character(1)
    )
    observations <- utils::read.csv(paths[["observations_prepared.csv"]])
    forcing <- utils::read.csv(paths[["climate_forcing.csv"]])
    bulk_density <- utils::read.csv(paths[["bulk_density.csv"]])
    predictions <- utils::read.csv(paths[["predictions.csv"]])
    parameters <- utils::read.csv(paths[["fit_parameters.csv"]])

    expect_equal(nrow(observations), case$observation_rows)
    expect_equal(nrow(forcing), case$forcing_rows)
    expect_equal(nrow(bulk_density), 3L)
    expect_equal(nrow(predictions), case$forcing_rows)
    expect_equal(nrow(parameters), 5L)
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
  }
})

test_that("reference outputs conserve mass and respect parameter bounds", {
  for (case_id in shared_reference_cases$case_id) {
    predictions <- utils::read.csv(expect_reference_file(
      case_id,
      "predictions.csv"
    ))
    parameters <- utils::read.csv(expect_reference_file(
      case_id,
      "fit_parameters.csv"
    ))
    total <- rowSums(predictions[c(
      "mass_top",
      "mass_bottom",
      "mass_below",
      "mass_degraded"
    )])

    expect_equal(total, rep(1, length(total)), tolerance = 1e-8)
    expect_true(all(is.finite(predictions$concentration_top_ug_kg)))
    expect_true(all(is.finite(predictions$concentration_bottom_ug_kg)))
    expect_true(all(parameters$estimate >= parameters$lower))
    expect_true(all(parameters$estimate <= parameters$upper))
  }
})
