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
  testthat::test_path("..", "..", "..", "examples", "data", ...)
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
