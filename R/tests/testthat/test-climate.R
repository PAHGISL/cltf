#!/usr/bin/env Rscript
# Script: test-climate.R
# Objective: Verify R temperature-based PET against the current Python reference values.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Daily day-of-year and maximum/minimum temperatures.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "climate").
# Dependencies: testthat, cltf

test_that("temperature PET matches the Python climate module", {
  result <- pet_from_temperature(
    jday        = c(164, 165, 166, 167, 168),
    tmax_c      = c(18.4, 19.2, 20.1, 17.8, 16.5),
    tmin_c      = c(7.1, 6.8, 8.0, 5.6, 4.9),
    latitude_deg = -32.85
  )

  expect_equal(result, c(1.2, 1.3, 1.3, 1.2, 1.1), tolerance = 1e-6)
})

test_that("temperature PET rejects maximum temperatures below minima", {
  expect_error(
    pet_from_temperature(164, 5, 6, -32.85),
    "below"
  )
})
