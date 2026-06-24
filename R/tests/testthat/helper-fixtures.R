#!/usr/bin/env Rscript
# Script: helper-fixtures.R
# Objective: Provide reusable validated layer fixtures for cltf tests.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: None.
# Outputs: Test helper functions.
# Usage: Loaded automatically by testthat.
# Dependencies: testthat, cltf

top_layer_fixture <- function() {
  cltf_layer(
    mu            = 1.0,
    sigma         = 0.5,
    retardation   = 2.0,
    thickness_mm  = 100.0
  )
}

bottom_layer_fixture <- function() {
  cltf_layer(
    mu            = 1.2,
    sigma         = 0.6,
    retardation   = 3.0,
    thickness_mm  = 200.0
  )
}
