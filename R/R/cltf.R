# Script: cltf.R
# Objective: Implement validated single- and two-layer CLTF transport calculations.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Layer parameters and cumulative infiltration values.
# Outputs: Transfer densities, cumulative probabilities, and layer mass fractions.
# Usage: Use exported functions after library(cltf).
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
#' @return A validated `cltf_layer` list.
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
    class = "cltf_layer"
  )
}

validate_layer <- function(layer) {
  if (!inherits(layer, "cltf_layer")) {
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

trapz_integral <- function(x, y) {
  sum(diff(x) * (y[-length(y)] + y[-1L]) / 2)
}

two_layer_cdf_scalar <- function(
  y_mm,
  top_layer,
  bottom_layer,
  method,
  n_steps,
  rel_tol
) {
  if (y_mm == 0) {
    return(0)
  }

  if (method == "adaptive") {
    integrand_log_y <- function(log_u) {
      u <- exp(log_u)
      stats::dnorm(
        log_u,
        mean = layer_meanlog(top_layer),
        sd   = top_layer$sigma
      ) * cltf_cdf(y_mm - u, bottom_layer)
    }

    return(stats::integrate(
      integrand_log_y,
      lower         = -Inf,
      upper         = log(y_mm),
      rel.tol       = rel_tol,
      subdivisions  = 1000L,
      stop.on.error = TRUE
    )$value)
  }

  grid <- seq(0, y_mm, length.out = n_steps)
  integrand <- cltf_pdf(grid, top_layer) *
    cltf_cdf(y_mm - grid, bottom_layer)
  trapz_integral(grid, integrand)
}

#' Evaluate the sequential two-layer CLTF CDF
#'
#' @param y_mm Non-negative cumulative infiltration values in millimetres.
#' @param top_layer,bottom_layer Validated layers from [cltf_layer()].
#' @param method Numerical method: `"adaptive"` or `"trapezoid"`.
#' @param n_steps Odd number of trapezoidal grid points.
#' @param rel_tol Adaptive integration relative tolerance.
#' @return Numeric cumulative probabilities of crossing both layers.
#' @export
cltf_two_layer_cdf <- function(
  y_mm,
  top_layer,
  bottom_layer,
  method  = c("adaptive", "trapezoid"),
  n_steps = 5001L,
  rel_tol = 1e-8
) {
  validate_layer(top_layer)
  validate_layer(bottom_layer)
  method <- match.arg(method)

  if (any(!is.finite(y_mm)) || any(y_mm < 0)) {
    stop("y_mm must contain finite non-negative values.", call. = FALSE)
  }
  if (length(n_steps) != 1L || n_steps < 3L || n_steps %% 2L == 0L) {
    stop("n_steps must be one odd integer of at least 3.", call. = FALSE)
  }
  validate_positive_scalar(rel_tol, "rel_tol")

  result <- vapply(
    y_mm,
    two_layer_cdf_scalar,
    numeric(1),
    top_layer    = top_layer,
    bottom_layer = bottom_layer,
    method       = method,
    n_steps      = as.integer(n_steps),
    rel_tol      = rel_tol
  )

  pmin(pmax(result, 0), 1)
}

validate_layer_probabilities <- function(result, tolerance) {
  if (any(result < -tolerance) ||
      any(result > 1 + tolerance) ||
      any(abs(rowSums(result) - 1) > tolerance)) {
    stop("Layer probabilities violate numerical mass balance.", call. = FALSE)
  }
  invisible(result)
}

#' Calculate resident mass fractions by layer
#'
#' @inheritParams cltf_two_layer_cdf
#' @param tolerance Numerical tolerance for probability validation.
#' @return Matrix with columns `top`, `bottom`, and `below`.
#' @export
cltf_layer_probabilities <- function(
  y_mm,
  top_layer,
  bottom_layer,
  method    = c("adaptive", "trapezoid"),
  n_steps   = 5001L,
  rel_tol   = 1e-8,
  tolerance = 1e-8
) {
  method <- match.arg(method)
  g1 <- cltf_cdf(y_mm, top_layer)
  g12 <- cltf_two_layer_cdf(
    y_mm,
    top_layer,
    bottom_layer,
    method  = method,
    n_steps = n_steps,
    rel_tol = rel_tol
  )
  result <- cbind(
    top    = 1 - g1,
    bottom = g1 - g12,
    below  = g12
  )

  validate_layer_probabilities(result, tolerance)
  result[result < 0 & result >= -tolerance] <- 0
  result / rowSums(result)
}
