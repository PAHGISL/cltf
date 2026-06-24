#!/usr/bin/env Rscript
# Script: test-reference-runner.R
# Objective: Verify the shared R reference runner command-line interface.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: R reference runner script.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "reference-runner").
# Dependencies: testthat

test_that("reference runner accepts both case identifiers", {
  script <- testthat::test_path(
    "..",
    "..",
    "..",
    "examples",
    "R",
    "run_reference_case.R"
  )
  if (!file.exists(script)) {
    skip("The shared R reference runner is available only from a source checkout.")
  }
  help <- system2("Rscript", c(script, "--help"), stdout = TRUE)

  expect_true(any(grepl("--case", help, fixed = TRUE)))
  expect_true(any(grepl("nsw_griffith_heavy_imazapic", help, fixed = TRUE)))
  expect_true(any(grepl("sa_minnipa_heavy_imazapic", help, fixed = TRUE)))
})
