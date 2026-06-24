#!/usr/bin/env Rscript
# Script: test-concentration.R
# Objective: Verify degradation, soil-mass, and resident-concentration calculations.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: cltf mass and concentration functions.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "concentration").
# Dependencies: testthat, cltf

test_that("soil mass uses depth interval and bulk density", {
  expect_equal(
    soil_mass_kg_ha(0, 100, bulk_density_g_cm3 = 1.3),
    1.3e6
  )
  expect_equal(
    soil_mass_kg_ha(100, 300, bulk_density_g_cm3 = 1.3),
    2.6e6
  )
})

test_that("concentration conversion reproduces application-rate arithmetic", {
  result <- resident_concentration_ug_kg(
    application_rate_g_ha = 21.32,
    remaining_fraction    = 1,
    soil_mass_kg_ha       = 1.3e6,
    effective_porosity    = 0.2
  )

  expect_equal(result, 16.4, tolerance = 1e-10)
})

test_that("effective porosity is a normalized concentration scale", {
  base <- resident_concentration_ug_kg(20, 0.5, 1e6, 0.2)
  half <- resident_concentration_ug_kg(20, 0.5, 1e6, 0.4)

  expect_equal(half, base / 2)
})

test_that("degradation balance includes degraded mass", {
  result <- apply_elapsed_degradation(
    layer_probabilities = matrix(c(0.4, 0.3, 0.3), nrow = 1),
    time_days           = 100,
    decay_rate_day      = 0.01
  )

  expect_equal(rowSums(result), 1, tolerance = 1e-12)
})
