#!/usr/bin/env Rscript
# Script: test-package.R
# Objective: Verify that the rclt package metadata loads under testthat.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Installed rclt package metadata.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("rclt").
# Dependencies: testthat, rclt

test_that("package metadata is available", {
  expect_equal(as.character(utils::packageVersion("rclt")), "0.1.0")
})
