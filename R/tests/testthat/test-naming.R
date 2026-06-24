#!/usr/bin/env Rscript
# Script: test-naming.R
# Objective: Prevent legacy package names from returning to active R files.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Active R package and shared reference text files.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "naming").
# Dependencies: testthat, cltf

test_that("active R text files contain no legacy branding", {
  repository_root <- normalizePath(
    testthat::test_path("..", "..", ".."),
    mustWork = TRUE
  )
  files <- c(
    list.files(file.path(repository_root, "R"), recursive = TRUE, full.names = TRUE),
    list.files(
      file.path(repository_root, "examples", "R"),
      recursive = TRUE,
      full.names = TRUE
    ),
    list.files(
      file.path(repository_root, "reference"),
      recursive = TRUE,
      full.names = TRUE
    )
  )
  files <- files[grepl("\\.(R|md|json|Rd)$", files)]
  text <- unlist(lapply(files, readLines, warn = FALSE), use.names = FALSE)

  legacy_pattern <- paste(
    c("r", "R", "py", "Py"),
    c("clt", "CLT", "clt", "CLT"),
    sep      = "",
    collapse = "|"
  )
  expect_false(any(grepl(legacy_pattern, text)))
})
