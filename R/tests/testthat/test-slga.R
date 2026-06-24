#!/usr/bin/env Rscript
# Script: test-slga.R
# Objective: Verify SLGA bulk-density parsing, depth weighting, and manual overrides.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Cached SLGA JSON fixtures and bulk-density overrides.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "slga").
# Dependencies: testthat, rclt, withr

test_that("SLGA bulk-density fixture parses to standard depth bands", {
  path <- system.file(
    "extdata",
    "slga_bulk_density_response.json",
    package = "rclt"
  )
  bands <- parse_slga_bulk_density(path)

  expect_equal(bands$depth_top_mm, c(0, 50, 150))
  expect_equal(bands$depth_bottom_mm, c(50, 150, 300))
  expect_equal(bands$estimate_g_cm3, c(1.32, 1.38, 1.43))
})

test_that("bulk density is weighted by depth overlap", {
  path <- system.file(
    "extdata",
    "slga_bulk_density_response.json",
    package = "rclt"
  )
  bands <- parse_slga_bulk_density(path)
  top <- weight_bulk_density(bands, 0, 100)
  bottom <- weight_bulk_density(bands, 100, 300)

  expect_equal(top$estimate_g_cm3, 1.35)
  expect_equal(bottom$estimate_g_cm3, 1.4175)
})

test_that("manual override bypasses SLGA network access", {
  cache_dir <- withr::local_tempdir()
  result <- fetch_slga_bulk_density(
    latitude        = -32.831016,
    longitude       = 135.14494,
    cache_dir       = cache_dir,
    manual_override = c(1.32, 1.38, 1.43),
    metadata_reader = function(...) stop("network metadata was requested"),
    drill_reader    = function(...) stop("network drill was requested")
  )

  expect_equal(result$estimate_g_cm3, c(1.32, 1.38, 1.43))
  expect_true(all(result$source == "manual_override"))
})

test_that("SLGA product metadata is drilled and normalized into the cache", {
  cache_dir <- withr::local_tempdir()
  depths <- c("000_005", "005_015", "015_030")
  statistics <- c("Modelled-Value", "Lower-CI", "Upper-CI")
  products <- expand.grid(
    depth     = depths,
    Component = statistics,
    stringsAsFactors = FALSE
  )
  products$COGPath <- paste0(
    "https://example.test/BDW_",
    products$depth,
    "_",
    c("EV", "05", "95")[match(products$Component, statistics)],
    ".tif"
  )
  values <- c(1.32, 1.38, 1.43, 1.18, 1.22, 1.28, 1.46, 1.54, 1.58)
  counter <- 0L
  drill_reader <- function(...) {
    counter <<- counter + 1L
    list(value = values[counter])
  }

  result <- fetch_slga_bulk_density(
    latitude        = -32.831016,
    longitude       = 135.14494,
    cache_dir       = cache_dir,
    api_key         = "test-key-not-for-cache",
    metadata_reader = function(...) products,
    drill_reader    = drill_reader
  )

  expect_equal(result$depth_bottom_mm, c(50, 150, 300))
  expect_equal(result$estimate_g_cm3, c(1.32, 1.38, 1.43))
  cache_text <- paste(readLines(attr(result, "cache_path")), collapse = "\n")
  expect_false(grepl("test-key-not-for-cache", cache_text, fixed = TRUE))
})
