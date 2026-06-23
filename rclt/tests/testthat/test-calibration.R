#!/usr/bin/env Rscript
# Script: test-calibration.R
# Objective: Verify replicate-level log-space RCLT calibration and profiles.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Deterministic synthetic forcing and concentration observations.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "calibration").
# Dependencies: testthat, rclt

synthetic_calibration_case <- function() {
  truth <- c(
    mu       = 1.0,
    sigma    = 0.5,
    R_top    = 2.0,
    R_bottom = 3.0,
    k        = 0.005
  )
  forcing <- data.frame(
    time_days                  = seq(5, 120, length.out = 12),
    cumulative_infiltration_mm = seq(80, 1400, length.out = 12)
  )
  simulation <- simulate_rclt(
    time_days                   = forcing$time_days,
    cumulative_infiltration_mm = forcing$cumulative_infiltration_mm,
    top_layer                  = cltf_layer(
      truth["mu"],
      truth["sigma"],
      truth["R_top"],
      100
    ),
    bottom_layer               = cltf_layer(
      truth["mu"],
      truth["sigma"],
      truth["R_bottom"],
      200
    ),
    decay_rate_day             = truth["k"],
    application_rate_g_ha      = 30,
    top_bulk_density_g_cm3     = 1.35,
    bottom_bulk_density_g_cm3  = 1.42,
    method                      = "trapezoid",
    n_steps                     = 501
  )
  observations <- rbind(
    data.frame(
      days_since_application = forcing$time_days,
      depth_top_mm           = 0,
      depth_bottom_mm        = 100,
      concentration          = simulation$concentration_top_ug_kg
    ),
    data.frame(
      days_since_application = forcing$time_days,
      depth_top_mm           = 100,
      depth_bottom_mm        = 300,
      concentration          = simulation$concentration_bottom_ug_kg
    )
  )
  set.seed(42)
  observations$analysis_concentration_ug_kg <- observations$concentration *
    exp(stats::rnorm(nrow(observations), sd = 0.03))
  observations$concentration <- NULL

  list(truth = truth, forcing = forcing, observations = observations)
}

test_that("multistart calibration improves a finite replicate-level objective", {
  case <- synthetic_calibration_case()
  initial <- c(
    mu       = 0.45,
    sigma    = 0.9,
    R_top    = 4.5,
    R_bottom = 1.2,
    k        = 0.02
  )
  lower <- c(mu = 0.2, sigma = 0.15, R_top = 0.5, R_bottom = 0.5, k = 0)
  upper <- c(mu = 3, sigma = 1.5, R_top = 8, R_bottom = 8, k = 0.05)
  initial_objective <- rclt_objective(
    initial,
    case$observations,
    case$forcing,
    application_rate_g_ha     = 30,
    top_bulk_density_g_cm3    = 1.35,
    bottom_bulk_density_g_cm3 = 1.42,
    method                     = "trapezoid",
    n_steps                    = 501
  )
  fit <- fit_rclt(
    observations               = case$observations,
    forcing                    = case$forcing,
    application_rate_g_ha      = 30,
    top_bulk_density_g_cm3     = 1.35,
    bottom_bulk_density_g_cm3  = 1.42,
    lower                      = lower,
    upper                      = upper,
    initial                    = initial,
    n_starts                   = 3,
    seed                       = 123,
    method                     = "trapezoid",
    n_steps                    = 501,
    control                    = list(maxit = 60)
  )

  expect_true(is.finite(fit$objective))
  expect_lt(fit$objective, initial_objective)
  expect_true(all(fit$parameters >= lower))
  expect_true(all(fit$parameters <= upper))
  expect_named(fit$bound_hit, names(lower))
  expect_equal(nrow(fit$predictions), nrow(case$observations))
})

test_that("calibration is deterministic for a fixed seed", {
  case <- synthetic_calibration_case()
  arguments <- list(
    observations               = case$observations,
    forcing                    = case$forcing,
    application_rate_g_ha      = 30,
    top_bulk_density_g_cm3     = 1.35,
    bottom_bulk_density_g_cm3  = 1.42,
    n_starts                   = 2,
    seed                       = 99,
    method                     = "trapezoid",
    n_steps                    = 301,
    control                    = list(maxit = 20)
  )

  first <- do.call(fit_rclt, arguments)
  second <- do.call(fit_rclt, arguments)

  expect_equal(second$parameters, first$parameters)
  expect_equal(second$objective, first$objective)
  expect_equal(second$start_index, first$start_index)
})

test_that("objective profiles fix the selected parameter", {
  case <- synthetic_calibration_case()
  fit <- fit_rclt(
    observations               = case$observations,
    forcing                    = case$forcing,
    application_rate_g_ha      = 30,
    top_bulk_density_g_cm3     = 1.35,
    bottom_bulk_density_g_cm3  = 1.42,
    n_starts                   = 1,
    seed                       = 7,
    method                     = "trapezoid",
    n_steps                    = 301,
    control                    = list(maxit = 20)
  )
  grid <- fit$parameters["k"] * c(0.8, 1.2)
  profile <- profile_rclt_parameter(
    fit,
    parameter = "k",
    grid      = grid,
    control   = list(maxit = 10)
  )

  expect_equal(profile$parameter_value, as.numeric(grid))
  expect_true(all(is.finite(profile$objective)))
})
