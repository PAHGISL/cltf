#!/usr/bin/env Rscript
# Script: test-cltf-single-layer.R
# Objective: Verify the mathematical definition and validation of one CLTF layer.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-25
# Inputs: cltf single-layer functions.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "cltf-single-layer").
# Dependencies: testthat, cltf

test_that("cltf_layer validates physical parameters", {
  expect_error(cltf_layer(0, 0.5, 2, 100), "mu")
  expect_error(cltf_layer(1, 0, 2, 100), "sigma")
  expect_error(cltf_layer(1, 0.5, 0, 100), "retardation")
  expect_error(cltf_layer(1, 0.5, 2, 0), "thickness_mm")
})

test_that("single-layer functions match the equivalent lognormal", {
  layer   <- top_layer_fixture()
  y       <- c(0, 50, 100, 200, 500)
  meanlog <- log(layer$mu * layer$retardation * layer$thickness_mm)

  expect_equal(
    cltf_pdf(y, layer),
    stats::dlnorm(y, meanlog = meanlog, sdlog = layer$sigma)
  )
  expect_equal(
    cltf_cdf(y, layer),
    stats::plnorm(y, meanlog = meanlog, sdlog = layer$sigma)
  )
})

test_that("single-layer density normalizes to one", {
  layer <- top_layer_fixture()
  result <- integrate(
    function(y) cltf_pdf(y, layer),
    lower   = 0,
    upper   = Inf,
    rel.tol = 1e-10
  )

  expect_equal(result$value, 1, tolerance = 1e-8)
})

test_that("continuous interval probabilities follow depth crossing CDF", {
  y <- c(0, 100, 400)
  intervals <- data.frame(
    depth_top_mm    = c(0, 100),
    depth_bottom_mm = c(100, 300)
  )

  result <- cltf_interval_probabilities(
    y_mm        = y,
    intervals   = intervals,
    mu          = 1,
    sigma       = 0.5,
    retardation = 2
  )
  crossing_100 <- cltf_depth_cdf(
    y_mm        = y,
    depth_mm    = 100,
    mu          = 1,
    sigma       = 0.5,
    retardation = 2
  )
  crossing_300 <- cltf_depth_cdf(
    y_mm        = y,
    depth_mm    = 300,
    mu          = 1,
    sigma       = 0.5,
    retardation = 2
  )

  expect_equal(result[, "0-100"], 1 - crossing_100)
  expect_equal(result[, "100-300"], crossing_100 - crossing_300)
  expect_equal(result[, "below"], crossing_300)
  expect_equal(rowSums(result), c(1, 1, 1), tolerance = 1e-12)
})
