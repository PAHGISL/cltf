#!/usr/bin/env Rscript
# Script: test-cltf-two-layer.R
# Objective: Verify two-layer convolution and conservative layer partitioning.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: rclt two-layer CLTF functions.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "cltf-two-layer").
# Dependencies: testthat, rclt

test_that("adaptive and trapezoidal convolution agree", {
  top      <- top_layer_fixture()
  bottom   <- bottom_layer_fixture()
  y        <- c(25, 100, 250, 500, 1000)
  adaptive <- cltf_two_layer_cdf(y, top, bottom, method = "adaptive")
  trapezoid <- cltf_two_layer_cdf(
    y,
    top,
    bottom,
    method  = "trapezoid",
    n_steps = 20001L
  )

  expect_equal(trapezoid, adaptive, tolerance = 2e-4)
})

test_that("layer probabilities are non-negative and sum to one", {
  result <- cltf_layer_probabilities(
    y_mm         = c(0, 25, 100, 500, 5000),
    top_layer    = top_layer_fixture(),
    bottom_layer = bottom_layer_fixture()
  )

  expect_true(all(result >= 0))
  expect_equal(rowSums(result), rep(1, nrow(result)), tolerance = 1e-10)
  expect_equal(unname(result[1, ]), c(1, 0, 0))
})

test_that("large infiltration moves mass below the model profile", {
  result <- cltf_layer_probabilities(
    y_mm         = 1e8,
    top_layer    = top_layer_fixture(),
    bottom_layer = bottom_layer_fixture()
  )

  expect_lt(result[1, "top"], 1e-8)
  expect_lt(result[1, "bottom"], 1e-8)
  expect_equal(unname(result[1, "below"]), 1, tolerance = 1e-8)
})
