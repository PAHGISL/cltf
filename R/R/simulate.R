# Script: simulate.R
# Objective: Run conservative two-layer CLTF simulations over forcing time series.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Time, cumulative infiltration, layer parameters, degradation, mass, and soil properties.
# Outputs: Time-indexed mass fractions and resident concentrations.
# Usage: Use simulate_cltf() after library(cltf).
# Dependencies: base R

#' Simulate a two-layer CLTF time series
#'
#' @param time_days Non-decreasing elapsed times.
#' @param cumulative_infiltration_mm Non-decreasing cumulative infiltration.
#' @param top_layer,bottom_layer Validated CLTF layers.
#' @param decay_rate_day Global first-order degradation rate.
#' @param application_rate_g_ha Application rate in grams per hectare.
#' @param top_bulk_density_g_cm3,bottom_bulk_density_g_cm3 Layer bulk densities.
#' @param effective_porosity Empirical concentration scale.
#' @param method,n_steps,rel_tol Convolution settings.
#' @return Data frame of forcing, mass balance, and layer concentrations.
#' @export
simulate_cltf <- function(
  time_days,
  cumulative_infiltration_mm,
  top_layer,
  bottom_layer,
  decay_rate_day,
  application_rate_g_ha,
  top_bulk_density_g_cm3,
  bottom_bulk_density_g_cm3,
  effective_porosity = 0.2,
  method             = c("adaptive", "trapezoid"),
  n_steps            = 5001L,
  rel_tol            = 1e-8
) {
  method <- match.arg(method)
  if (length(time_days) == 0L ||
      length(time_days) != length(cumulative_infiltration_mm)) {
    stop("Time and infiltration vectors must have equal non-zero lengths.", call. = FALSE)
  }
  if (any(!is.finite(time_days)) ||
      any(time_days < 0) ||
      any(diff(time_days) < 0)) {
    stop(
      "time_days must be finite, non-negative, and non-decreasing.",
      call. = FALSE
    )
  }
  if (any(!is.finite(cumulative_infiltration_mm)) ||
      any(cumulative_infiltration_mm < 0) ||
      any(diff(cumulative_infiltration_mm) < 0)) {
    stop(
      "Cumulative infiltration must be finite, non-negative, and non-decreasing.",
      call. = FALSE
    )
  }

  probabilities <- cltf_layer_probabilities(
    cumulative_infiltration_mm,
    top_layer,
    bottom_layer,
    method  = method,
    n_steps = n_steps,
    rel_tol = rel_tol
  )
  balance <- apply_elapsed_degradation(
    probabilities,
    time_days,
    decay_rate_day
  )

  top_soil_mass <- soil_mass_kg_ha(
    0,
    top_layer$thickness_mm,
    top_bulk_density_g_cm3
  )
  bottom_soil_mass <- soil_mass_kg_ha(
    top_layer$thickness_mm,
    top_layer$thickness_mm + bottom_layer$thickness_mm,
    bottom_bulk_density_g_cm3
  )

  data.frame(
    time_days                  = time_days,
    cumulative_infiltration_mm = cumulative_infiltration_mm,
    mass_top                   = balance[, "top"],
    mass_bottom                = balance[, "bottom"],
    mass_below                 = balance[, "below"],
    mass_degraded              = balance[, "degraded"],
    concentration_top_ug_kg    = resident_concentration_ug_kg(
      application_rate_g_ha,
      balance[, "top"],
      top_soil_mass,
      effective_porosity
    ),
    concentration_bottom_ug_kg = resident_concentration_ug_kg(
      application_rate_g_ha,
      balance[, "bottom"],
      bottom_soil_mass,
      effective_porosity
    ),
    check.names = FALSE
  )
}
