#!/usr/bin/env Rscript
# Script: test-silo.R
# Objective: Verify SILO coordinate rounding, CSV parsing, and cache-first retrieval.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Cached SILO CSV fixtures and injected download functions.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt", filter = "silo").
# Dependencies: testthat, rclt, withr

test_that("SILO coordinates round to the nearest grid cell", {
  expect_equal(round_silo_coordinate(-32.831016), -32.85)
  expect_equal(round_silo_coordinate(135.14494), 135.15)
})

test_that("SILO CSV parser returns standard forcing fields", {
  path <- system.file("extdata", "sa_silo.csv", package = "rclt")
  result <- parse_silo_csv(path)

  expect_equal(
    names(result),
    c("date", "jdays", "rain_mm", "Tmax", "Tmin")
  )
  expect_equal(result$date, as.Date(c("2024-06-12", "2024-06-13")))
  expect_equal(result$jdays, c(164L, 165L))
  expect_equal(result$rain_mm, c(0, 3.4))
})

test_that("SILO retrieval reuses an existing cache", {
  cache_dir <- withr::local_tempdir()
  fixture <- system.file("extdata", "sa_silo.csv", package = "rclt")
  calls <- 0L
  downloader <- function(url, destfile, quiet, mode) {
    calls <<- calls + 1L
    file.copy(fixture, destfile)
  }

  first <- fetch_silo_point(
    latitude   = -32.831016,
    longitude  = 135.14494,
    start_date = as.Date("2024-06-12"),
    end_date   = as.Date("2024-06-13"),
    cache_dir  = cache_dir,
    username   = "test@example.org",
    password   = "testpassword",
    downloader = downloader
  )
  second <- fetch_silo_point(
    latitude   = -32.831016,
    longitude  = 135.14494,
    start_date = as.Date("2024-06-12"),
    end_date   = as.Date("2024-06-13"),
    cache_dir  = cache_dir,
    downloader = function(...) stop("cache was not used")
  )

  expect_equal(calls, 1L)
  expect_equal(second, first)
  expect_true(file.exists(attr(second, "metadata_path")))
})
