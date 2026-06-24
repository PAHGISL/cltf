#!/usr/bin/env Rscript
# Script: test-cltf-single-layer.R
# Objective: Verify the mathematical definition and validation of one CLTF layer.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: rclt single-layer functions.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "cltf-single-layer").
# Dependencies: testthat, rclt

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
