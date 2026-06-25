#!/usr/bin/env Rscript
# Script: test-simulate.R
# Objective: Verify end-to-end time-series CLTF simulation and limiting cases.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-25
# Inputs: cltf simulator and fixed model inputs.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "simulate").
# Dependencies: testthat, cltf

test_that("simulation starts with all undegraded mass in the top layer", {
  result <- simulate_cltf(
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
    simulate_cltf(
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

test_that("one-layer interval simulation accepts arbitrary depths", {
  intervals <- data.frame(
    depth_top_mm       = c(0, 50, 150),
    depth_bottom_mm    = c(50, 150, 300),
    bulk_density_g_cm3 = c(1.3, 1.35, 1.4)
  )

  result <- simulate_cltf_intervals(
    time_days                   = c(0, 60),
    cumulative_infiltration_mm = c(0, 400),
    intervals                  = intervals[c("depth_top_mm", "depth_bottom_mm")],
    mu                         = 1,
    sigma                      = 0.5,
    retardation                = 2,
    decay_rate_day             = 0.001,
    application_rate_g_ha      = 30,
    bulk_density_g_cm3         = intervals$bulk_density_g_cm3
  )

  expect_equal(nrow(result), 6)
  expect_equal(result$depth_top_mm, rep(c(0, 50, 150), 2))
  expect_true(all(result$concentration_ug_kg >= 0))
  grouped <- stats::aggregate(mass_fraction ~ time_days, result, sum)
  expect_equal(grouped$mass_fraction[grouped$time_days == 0], 1)
  expect_lt(grouped$mass_fraction[grouped$time_days == 60], 1)
})

test_that("one-layer profile peak moves down with infiltration", {
  depths <- seq(0, 300, length.out = 121)
  result <- simulate_cltf_profile(
    time_days                   = c(30, 60, 90),
    cumulative_infiltration_mm = c(120, 240, 360),
    depths_mm                  = depths,
    mu                         = 1,
    sigma                      = 0.5,
    retardation                = 2,
    decay_rate_day             = 0.001,
    application_rate_g_ha      = 30,
    bulk_density_g_cm3         = 1.35
  )

  peak_rows <- do.call(rbind, lapply(
    split(result, result$time_days),
    function(table) table[which.max(table$concentration_ug_kg), ]
  ))
  peak_rows <- peak_rows[order(peak_rows$time_days), ]
  surface <- result$concentration_ug_kg[result$depth_mm == 0]

  expect_true(all(surface == 0))
  expect_true(all(diff(peak_rows$depth_mm) > 0))
})
