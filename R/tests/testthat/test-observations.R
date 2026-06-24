#!/usr/bin/env Rscript
# Script: test-observations.R
# Objective: Verify observation intervals, non-detect handling, summaries, and mass inference.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Tidy observation values and site/depth labels.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "observations").
# Dependencies: testthat, rclt

test_that("site depth labels map to explicit sampling intervals", {
  expect_equal(depth_interval_mm("SA", "10cm"), c(0, 100))
  expect_equal(depth_interval_mm("SA", "30cm"), c(100, 300))
  expect_equal(depth_interval_mm("NSW", "15cm"), c(0, 150))
  expect_equal(depth_interval_mm("NSW", "30cm"), c(150, 300))
})

test_that("non-detects require explicit detection limits", {
  prepared <- prepare_non_detects(
    concentration_ug_kg   = c(2, 0, 0),
    is_non_detect         = c(FALSE, TRUE, FALSE),
    detection_limit_ug_kg = c(NA, 0.2, NA)
  )

  expect_equal(prepared$analysis_concentration_ug_kg, c(2, 0.1, NA))
  expect_true(prepared$excluded_zero[3])
  expect_true(prepared$lod_substituted[2])
})

test_that("geometric summaries are calculated in log space", {
  summary <- geometric_concentration(
    data.frame(
      group = c("a", "a", "a"),
      analysis_concentration_ug_kg = c(1, 2, 4)
    ),
    group_columns = "group"
  )

  expect_equal(summary$geometric_mean_ug_kg, 2)
  expect_equal(summary$n, 3)
})

test_that("application rate inference reverses concentration conversion", {
  result <- infer_application_rate_g_ha(
    t0_concentration_ug_kg = rep(16.4, 3),
    depth_top_mm           = 0,
    depth_bottom_mm        = 100,
    bulk_density_g_cm3     = 1.3
  )

  expect_equal(result, 21.32, tolerance = 1e-10)
})
