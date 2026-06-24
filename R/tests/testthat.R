#!/usr/bin/env Rscript
# Script: testthat.R
# Objective: Run the cltf package testthat suite.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Tests and package source under R.
# Outputs: Testthat results.
# Usage: Rscript -e 'testthat::test_local("R")'
# Dependencies: testthat, cltf

library(testthat)
library(cltf)

test_check("cltf")
