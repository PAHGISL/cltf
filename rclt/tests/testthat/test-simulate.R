#!/usr/bin/env Rscript
# Script: test-simulate.R
# Objective: Verify end-to-end time-series CLTF simulation and limiting cases.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: rclt simulator and fixed model inputs.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "simulate").
# Dependencies: testthat, rclt

test_that("simulation starts with all undegraded mass in the top layer", {
  result <- simulate_rclt(
    time_days                   = c(0, 10),
    cumulative_infiltration_mm = c(0, 0),
    top_layer                  = top_layer_fixture(),
    bottom_layer               = bottom_layer_fixture(),
    decay_rate_day             = 0.01,
    application_rate_g_ha      = 21.32,
    top_bulk_density_g_cm3     = 1.3,
    bottom_bulk_density_g_cm3  = 1.4
  )

  expect_equal(result$mass_top[1], 1)
  expect_equal(result$mass_bottom[1], 0)
  expect_equal(result$concentration_top_ug_kg[1], 16.4, tolerance = 1e-10)
  expect_equal(result$mass_top[2], exp(-0.1), tolerance = 1e-12)
  expect_equal(
    rowSums(
      result[c("mass_top", "mass_bottom", "mass_below", "mass_degraded")]
    ),
    c(1, 1)
  )
})

test_that("simulation rejects decreasing forcing", {
  expect_error(
    simulate_rclt(
      time_days                   = c(0, 2, 1),
      cumulative_infiltration_mm = c(0, 5, 10),
      top_layer                  = top_layer_fixture(),
      bottom_layer               = bottom_layer_fixture(),
      decay_rate_day             = 0.01,
      application_rate_g_ha      = 20,
      top_bulk_density_g_cm3     = 1.3,
      bottom_bulk_density_g_cm3  = 1.4
    ),
    "non-decreasing"
  )
})
