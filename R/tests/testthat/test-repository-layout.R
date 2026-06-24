#!/usr/bin/env Rscript
# Script: test-repository-layout.R
# Objective: Verify the CLTF monorepo uses the approved R and shared-data layout.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Repository-relative directories and package metadata.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "repository-layout").
# Dependencies: testthat, cltf

test_that("R package and shared references use approved paths", {
  repository_root <- normalizePath(
    testthat::test_path("..", "..", ".."),
    mustWork = TRUE
  )

  expect_true(file.exists(file.path(repository_root, "R", "DESCRIPTION")))
  expect_true(file.exists(file.path(repository_root, "reference")))
  expect_true(file.exists(file.path(
    repository_root,
    "examples",
    "R",
    "run_sa_reference.R"
  )))
  expect_false(file.exists(file.path(repository_root, "cltf")))
})
