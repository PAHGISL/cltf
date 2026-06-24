#!/usr/bin/env Rscript
# Script: test-plots.R
# Objective: Verify that all base-R CLTF diagnostic plots render to PNG files.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Small deterministic forcing, prediction, simulation, profile, and soil tables.
# Outputs: Non-empty temporary PNG files and testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "plots").
# Dependencies: testthat, cltf, withr

expect_cltf_plot <- function(draw) {
  path <- tempfile(fileext = ".png")
  grDevices::png(path, width = 900, height = 650, res = 120)
  device <- grDevices::dev.cur()
  on.exit({
    if (device %in% grDevices::dev.list()) {
      grDevices::dev.off(device)
    }
  }, add = TRUE)
  draw()
  grDevices::dev.off(device)

  expect_true(file.exists(path))
  expect_gt(file.info(path)$size, 0)
}

plot_test_data <- function() {
  time <- 0:5
  forcing <- data.frame(
    date                       = as.Date("2024-06-12") + time,
    time_days                  = time,
    rain_mm                    = c(0, 5, 0, 12, 1, 0),
    pet_mm                     = c(1.2, 1.3, 1.3, 1.1, 1.0, 1.2),
    daily_infiltration_mm      = c(0, 3.7, 0, 10.9, 0, 0),
    cumulative_infiltration_mm = c(0, 3.7, 3.7, 14.6, 14.6, 14.6)
  )
  simulation <- data.frame(
    time_days                  = time,
    cumulative_infiltration_mm = forcing$cumulative_infiltration_mm,
    mass_top                   = seq(1, 0.5, length.out = 6),
    mass_bottom                = seq(0, 0.25, length.out = 6),
    mass_below                 = seq(0, 0.1, length.out = 6),
    mass_degraded              = seq(0, 0.15, length.out = 6),
    concentration_top_ug_kg    = seq(16, 8, length.out = 6),
    concentration_bottom_ug_kg = seq(0.2, 2, length.out = 6)
  )
  predictions <- rbind(
    data.frame(
      days_since_application        = rep(time, each = 2),
      depth_top_mm                  = 0,
      depth_bottom_mm               = 100,
      replicate_id                  = rep(1:2, 6),
      analysis_concentration_ug_kg  = rep(seq(16, 8, length.out = 6), each = 2) *
        c(0.95, 1.05),
      predicted_concentration_ug_kg = rep(seq(15.5, 8.2, length.out = 6), each = 2)
    ),
    data.frame(
      days_since_application        = rep(time, each = 2),
      depth_top_mm                  = 100,
      depth_bottom_mm               = 300,
      replicate_id                  = rep(1:2, 6),
      analysis_concentration_ug_kg  = rep(seq(0.3, 2, length.out = 6), each = 2) *
        c(0.95, 1.05),
      predicted_concentration_ug_kg = rep(seq(0.25, 1.9, length.out = 6), each = 2)
    )
  )
  predictions$log_residual <- with(
    predictions,
    log(analysis_concentration_ug_kg) -
      log(predicted_concentration_ug_kg)
  )
  profile <- data.frame(
    parameter       = "k",
    parameter_value = seq(0.001, 0.01, length.out = 8),
    objective       = c(0.8, 0.5, 0.3, 0.2, 0.21, 0.3, 0.5, 0.75)
  )
  bulk_density <- data.frame(
    depth_top_mm    = c(0, 50, 150),
    depth_bottom_mm = c(50, 150, 300),
    estimate_g_cm3  = c(1.32, 1.38, 1.43),
    lower_g_cm3     = c(1.18, 1.22, 1.28),
    upper_g_cm3     = c(1.46, 1.54, 1.58),
    source           = "SLGA fixture"
  )
  list(
    forcing      = forcing,
    simulation   = simulation,
    predictions  = predictions,
    profile      = profile,
    bulk_density = bulk_density
  )
}

test_that("climate and soil input plots render", {
  data <- plot_test_data()
  expect_cltf_plot(function() plot_climate_forcing(data$forcing))
  expect_cltf_plot(function() plot_bulk_density(data$bulk_density))
})

test_that("fit diagnostic plots render", {
  data <- plot_test_data()
  expect_cltf_plot(function() plot_observed_fitted(data$predictions))
  expect_cltf_plot(function() plot_residuals(data$predictions))
  expect_cltf_plot(function() plot_objective_profile(data$profile))
})

test_that("mass diagnostic plots render", {
  data <- plot_test_data()
  expect_cltf_plot(function() plot_mass_fractions(data$simulation))
  expect_cltf_plot(function() plot_mass_balance(data$simulation))
})
