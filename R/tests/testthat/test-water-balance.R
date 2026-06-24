#!/usr/bin/env Rscript
# Script: test-water-balance.R
# Objective: Verify threshold water balance and generalized infiltration inverse.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Rainfall, irrigation, ET, cumulative infiltration, and target levels.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "water-balance").
# Dependencies: testthat, cltf

test_that("daily infiltration includes irrigation and ET thresholding", {
  expect_equal(
    daily_infiltration(
      rain_mm       = c(0, 10, 2),
      irrigation_mm = c(5, 0, 0),
      et_mm         = c(3, 3, 3),
      et_factor     = 1
    ),
    c(2, 7, 0)
  )
  expect_equal(
    cumulative_infiltration(c(0, 10, 2), c(3, 3, 3), c(5, 0, 0)),
    c(2, 9, 9)
  )
})

test_that("first-passage inverse selects the start of a plateau", {
  result <- first_passage_time(
    cumulative_infiltration_mm = c(0, 5, 5, 5, 9),
    time                       = 0:4,
    target_infiltration_mm     = c(0, 5, 6, 9, 10)
  )

  expect_equal(result, c(0, 1, 4, 4, NA_real_))
})

test_that("water balance rejects incompatible input lengths", {
  expect_error(
    daily_infiltration(c(1, 2), c(1), c(0, 0)),
    "equal lengths"
  )
})
