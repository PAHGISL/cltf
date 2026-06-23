#!/usr/bin/env Rscript
# Script: testthat.R
# Objective: Run the rclt package testthat suite.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Tests and package source under rclt.
# Outputs: Testthat results.
# Usage: Rscript -e 'testthat::test_local("rclt")'
# Dependencies: testthat, rclt

library(testthat)
library(rclt)

test_check("rclt")
