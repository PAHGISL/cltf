#!/usr/bin/env Rscript
# Script: test-package.R
# Objective: Verify that the cltf package metadata loads under testthat.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Installed cltf package metadata.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R").
# Dependencies: testthat, cltf

test_that("package metadata is available", {
  expect_equal(as.character(utils::packageVersion("cltf")), "0.1.0")
})
