# Script: cltf.R
# Objective: Implement validated single- and two-layer CLTF transport calculations.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Layer parameters and cumulative infiltration values.
# Outputs: Transfer densities, cumulative probabilities, and layer mass fractions.
# Usage: Use exported functions after library(rclt).
# Dependencies: stats

validate_positive_scalar <- function(value, name) {
  if (length(value) != 1L || !is.finite(value) || value <= 0) {
    stop(name, " must be one finite value greater than zero.", call. = FALSE)
  }
  invisible(value)
}

#' Define one CLTF soil layer
#'
#' @param mu Positive lognormal scale parameter.
#' @param sigma Positive lognormal log-scale standard deviation.
#' @param retardation Positive retardation factor.
#' @param thickness_mm Positive layer thickness in millimetres.
#' @return A validated `rclt_layer` list.
#' @export
cltf_layer <- function(mu, sigma, retardation, thickness_mm) {
  validate_positive_scalar(mu, "mu")
  validate_positive_scalar(sigma, "sigma")
  validate_positive_scalar(retardation, "retardation")
  validate_positive_scalar(thickness_mm, "thickness_mm")

  structure(
    list(
      mu           = as.numeric(mu),
      sigma        = as.numeric(sigma),
      retardation  = as.numeric(retardation),
      thickness_mm = as.numeric(thickness_mm)
    ),
    class = "rclt_layer"
  )
}

validate_layer <- function(layer) {
  if (!inherits(layer, "rclt_layer")) {
    stop("layer must be created by cltf_layer().", call. = FALSE)
  }
  invisible(layer)
}

layer_meanlog <- function(layer) {
  validate_layer(layer)
  log(layer$mu * layer$retardation * layer$thickness_mm)
}

#' Evaluate a single-layer CLTF density
#'
#' @param y_mm Non-negative cumulative infiltration values in millimetres.
#' @param layer A validated layer from [cltf_layer()].
#' @return Numeric density values.
#' @export
cltf_pdf <- function(y_mm, layer) {
  validate_layer(layer)
  if (any(!is.finite(y_mm)) || any(y_mm < 0)) {
    stop("y_mm must contain finite non-negative values.", call. = FALSE)
  }
  stats::dlnorm(
    y_mm,
    meanlog = layer_meanlog(layer),
    sdlog   = layer$sigma
  )
}

#' Evaluate a single-layer CLTF cumulative distribution
#'
#' @inheritParams cltf_pdf
#' @return Numeric cumulative probabilities.
#' @export
cltf_cdf <- function(y_mm, layer) {
  validate_layer(layer)
  if (any(!is.finite(y_mm)) || any(y_mm < 0)) {
    stop("y_mm must contain finite non-negative values.", call. = FALSE)
  }
  stats::plnorm(
    y_mm,
    meanlog = layer_meanlog(layer),
    sdlog   = layer$sigma
  )
}
