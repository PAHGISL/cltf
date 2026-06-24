#!/usr/bin/env Rscript
# Script: test-shared-conformance.R
# Objective: Verify R primitives against shared language-neutral outputs.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Shared primitive and tolerance JSON fixtures.
# Outputs: Testthat assertions.
# Usage: Loaded by testthat::test_local("R", filter = "shared-conformance").
# Dependencies: testthat, cltf, jsonlite

shared_reference_path <- function(filename) {
  path <- testthat::test_path("..", "..", "..", "reference", filename)
  if (!file.exists(path)) {
    skip("Shared primitive reference files are available only from a source checkout.")
  }
  path
}

test_that("R primitives match shared expected outputs", {
  primitive <- jsonlite::fromJSON(
    shared_reference_path("primitives.json"),
    simplifyVector = TRUE
  )
  tolerance <- jsonlite::fromJSON(
    shared_reference_path("tolerances.json"),
    simplifyVector = TRUE
  )

  pet <- primitive$pet
  expect_equal(
    do.call(pet_from_temperature, pet$inputs),
    pet$expected_mm_day,
    tolerance = tolerance$absolute
  )

  water <- primitive$water_balance
  expect_equal(
    do.call(daily_infiltration, water$inputs),
    water$expected_daily_mm,
    tolerance = tolerance$absolute
  )
  expect_equal(
    do.call(cumulative_infiltration, water$inputs),
    water$expected_cumulative_mm,
    tolerance = tolerance$absolute
  )

  passage <- primitive$first_passage
  expect_equal(
    do.call(first_passage_time, passage$inputs),
    passage$expected_time,
    tolerance = tolerance$absolute
  )

  single <- primitive$single_layer
  single_layer <- do.call(cltf_layer, single$layer)
  expect_equal(
    cltf_pdf(single$y_mm, single_layer),
    single$expected_pdf,
    tolerance = tolerance$absolute
  )
  expect_equal(
    cltf_cdf(single$y_mm, single_layer),
    single$expected_cdf,
    tolerance = tolerance$absolute
  )

  two <- primitive$two_layer
  two_tolerance <- if (two$method == "trapezoid") {
    tolerance$trapezoid_absolute
  } else {
    tolerance$absolute
  }
  expect_equal(
    unname(cltf_layer_probabilities(
      y_mm        = two$y_mm,
      top_layer   = do.call(cltf_layer, two$top_layer),
      bottom_layer = do.call(cltf_layer, two$bottom_layer),
      method      = two$method,
      n_steps     = two$n_steps
    )),
    unname(two$expected_probabilities),
    tolerance = two_tolerance
  )

  concentration <- primitive$concentration
  expect_equal(
    do.call(resident_concentration_ug_kg, concentration$inputs),
    concentration$expected_ug_kg,
    tolerance = tolerance$absolute
  )

  degradation <- primitive$degradation
  expect_equal(
    unname(do.call(apply_elapsed_degradation, degradation$inputs)),
    unname(degradation$expected_fractions),
    tolerance = tolerance$absolute
  )
})
