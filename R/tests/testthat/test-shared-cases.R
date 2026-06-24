#!/usr/bin/env Rscript
# Script: test-shared-cases.R
# Objective: Verify shared NSW and SA site/case inputs and normalized datasets.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Shared JSON, observation CSV, SILO CSV, and bulk-density inputs.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "shared-cases").
# Dependencies: testthat, cltf, jsonlite

shared_case_path <- function(...) {
  path <- testthat::test_path("..", "..", "..", "examples", "data", ...)
  if (!file.exists(path)) {
    skip("Shared case input files are available only from a source checkout.")
  }
  path
}

test_that("shared case registry defines both approved sites", {
  sites <- jsonlite::fromJSON(shared_case_path("sites.json"))
  expect_equal(sites$site_id, c("NSW_Griffith", "SA_Minnipa"))
  expect_equal(sites$top_depth_mm, c(150, 100))
  expect_equal(sites$bottom_depth_mm, c(300, 300))
})

test_that("case configurations define approved showcase periods", {
  nsw <- jsonlite::fromJSON(shared_case_path(
    "nsw_griffith_heavy_imazapic",
    "case.json"
  ))
  sa <- jsonlite::fromJSON(shared_case_path(
    "sa_minnipa_heavy_imazapic",
    "case.json"
  ))

  expect_equal(nsw$soil_group, "Heavy")
  expect_equal(nsw$herbicide, "Imazapic")
  expect_equal(nsw$application_date, "2024-04-26")
  expect_equal(nsw$final_date, "2024-09-19")
  expect_equal(sa$application_date, "2024-06-12")
  expect_equal(sa$final_date, "2024-10-28")
})

test_that("shared showcase observations preserve replicate rows", {
  nsw <- utils::read.csv(shared_case_path(
    "nsw_griffith_heavy_imazapic",
    "observations.csv"
  ))
  sa <- utils::read.csv(shared_case_path(
    "sa_minnipa_heavy_imazapic",
    "observations.csv"
  ))

  expect_equal(nrow(nsw), 30)
  expect_equal(sum(nsw$used_for_calibration), 24)
  expect_equal(sort(unique(nsw$depth_bottom_mm)), c(150, 300))
  expect_equal(nrow(sa), 31)
  expect_equal(sum(sa$used_for_calibration), 25)
})

test_that("shared SILO forcing covers each observation period", {
  nsw <- parse_silo_csv(shared_case_path(
    "nsw_griffith_heavy_imazapic",
    "silo.csv"
  ))
  sa <- parse_silo_csv(shared_case_path(
    "sa_minnipa_heavy_imazapic",
    "silo.csv"
  ))

  expect_equal(nrow(nsw), 147)
  expect_equal(range(nsw$date), as.Date(c("2024-04-26", "2024-09-19")))
  expect_equal(nrow(sa), 139)
  expect_equal(range(sa$date), as.Date(c("2024-06-12", "2024-10-28")))
})

test_that("shared SLGA bulk-density inputs cover standard bands", {
  nsw_path <- shared_case_path(
    "nsw_griffith_heavy_imazapic",
    "bulk_density.json"
  )
  sa_path <- shared_case_path(
    "sa_minnipa_heavy_imazapic",
    "bulk_density.json"
  )
  nsw <- parse_slga_bulk_density(nsw_path)
  sa <- parse_slga_bulk_density(sa_path)

  expect_equal(nsw$depth_top_mm, c(0, 50, 150))
  expect_equal(nsw$depth_bottom_mm, c(50, 150, 300))
  expect_equal(sa$depth_top_mm, c(0, 50, 150))
  expect_equal(sa$depth_bottom_mm, c(50, 150, 300))
  expect_true(all(grepl(
    "credentialed SLGA v2 whole-earth",
    nsw$source,
    fixed = TRUE
  )))
  expect_true(any(grepl(
    "provisional",
    sa$source,
    ignore.case = TRUE
  )))
})
