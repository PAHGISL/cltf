# Script: concentration.R
# Objective: Convert CLTF mass fractions into layer-average dry-soil concentrations.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Application rate, layer mass fractions, depth, bulk density, and porosity.
# Outputs: Soil masses, degraded mass fractions, and concentrations in micrograms per kilogram.
# Usage: Use exported functions after library(rclt).
# Dependencies: base R

#' Calculate dry soil mass per hectare
#'
#' @param depth_top_mm,depth_bottom_mm Layer bounds in millimetres.
#' @param bulk_density_g_cm3 Whole-earth bulk density in grams per cubic centimetre.
#' @return Dry soil mass in kilograms per hectare.
#' @export
soil_mass_kg_ha <- function(
  depth_top_mm,
  depth_bottom_mm,
  bulk_density_g_cm3
) {
  values <- c(depth_top_mm, depth_bottom_mm, bulk_density_g_cm3)
  if (any(!is.finite(values))) {
    stop("Depth and bulk density values must be finite.", call. = FALSE)
  }
  if (length(depth_top_mm) != 1L ||
      length(depth_bottom_mm) != 1L ||
      depth_top_mm < 0 ||
      depth_bottom_mm <= depth_top_mm) {
    stop("depth_bottom_mm must be greater than depth_top_mm.", call. = FALSE)
  }
  if (length(bulk_density_g_cm3) != 1L || bulk_density_g_cm3 <= 0) {
    stop("bulk_density_g_cm3 must be greater than zero.", call. = FALSE)
  }

  thickness_m  <- (depth_bottom_mm - depth_top_mm) / 1000
  density_kg_m3 <- bulk_density_g_cm3 * 1000
  10000 * thickness_m * density_kg_m3
}

#' Apply total elapsed-time degradation
#'
#' @param layer_probabilities Matrix with top, bottom, and below fractions.
#' @param time_days Non-negative elapsed times.
#' @param decay_rate_day Non-negative first-order rate per day.
#' @return Matrix with top, bottom, below, and degraded fractions.
#' @export
apply_elapsed_degradation <- function(
  layer_probabilities,
  time_days,
  decay_rate_day
) {
  if (!is.matrix(layer_probabilities) ||
      ncol(layer_probabilities) != 3L ||
      any(!is.finite(layer_probabilities)) ||
      any(layer_probabilities < 0) ||
      any(abs(rowSums(layer_probabilities) - 1) > 1e-8)) {
    stop(
      "layer_probabilities must be a finite three-column probability matrix.",
      call. = FALSE
    )
  }
  if (any(!is.finite(time_days)) || any(time_days < 0)) {
    stop("time_days must contain finite non-negative values.", call. = FALSE)
  }
  if (length(decay_rate_day) != 1L ||
      !is.finite(decay_rate_day) ||
      decay_rate_day < 0) {
    stop("decay_rate_day must be one finite non-negative value.", call. = FALSE)
  }
  if (nrow(layer_probabilities) != length(time_days)) {
    stop("One elapsed time is required per probability row.", call. = FALSE)
  }

  remaining <- exp(-decay_rate_day * time_days)
  result <- cbind(
    sweep(layer_probabilities, 1, remaining, `*`),
    degraded = 1 - remaining
  )
  colnames(result)[seq_len(3)] <- c("top", "bottom", "below")
  result
}

#' Convert remaining mass to resident concentration
#'
#' @param application_rate_g_ha Applied active ingredient in grams per hectare.
#' @param remaining_fraction Remaining mass fraction assigned to a layer.
#' @param soil_mass_kg_ha Dry soil mass represented by that layer.
#' @param effective_porosity Empirical concentration scale; 0.2 is neutral.
#' @return Resident concentration in micrograms per kilogram dry soil.
#' @export
resident_concentration_ug_kg <- function(
  application_rate_g_ha,
  remaining_fraction,
  soil_mass_kg_ha,
  effective_porosity = 0.2
) {
  values <- c(
    application_rate_g_ha,
    remaining_fraction,
    soil_mass_kg_ha,
    effective_porosity
  )
  if (any(!is.finite(values)) ||
      length(application_rate_g_ha) != 1L ||
      application_rate_g_ha < 0 ||
      any(remaining_fraction < 0) ||
      any(remaining_fraction > 1) ||
      length(soil_mass_kg_ha) != 1L ||
      soil_mass_kg_ha <= 0 ||
      length(effective_porosity) != 1L ||
      effective_porosity <= 0) {
    stop("Mass, fraction, soil mass, and porosity inputs are invalid.", call. = FALSE)
  }

  application_rate_g_ha * 1e6 / soil_mass_kg_ha *
    remaining_fraction * (0.2 / effective_porosity)
}
