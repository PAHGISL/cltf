# Script: simulate.R
# Objective: Run conservative two-layer CLTF simulations over forcing time series.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-25
# Inputs: Time, cumulative infiltration, layer parameters, degradation, mass, and soil properties.
# Outputs: Time-indexed mass fractions and resident concentrations.
# Usage: Use simulate_cltf() after library(cltf).
# Dependencies: base R

validate_forcing <- function(
  time_days,
  cumulative_infiltration_mm
) {
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
  invisible(TRUE)
}

validate_interval_density <- function(bulk_density_g_cm3, n_intervals) {
  if (length(bulk_density_g_cm3) == 1L) {
    bulk_density_g_cm3 <- rep(bulk_density_g_cm3, n_intervals)
  }
  if (length(bulk_density_g_cm3) != n_intervals ||
      any(!is.finite(bulk_density_g_cm3)) ||
      any(bulk_density_g_cm3 <= 0)) {
    stop(
      "bulk_density_g_cm3 must be one positive value per depth interval.",
      call. = FALSE
    )
  }
  as.numeric(bulk_density_g_cm3)
}

#' Simulate continuous one-layer CLTF concentration for depth intervals
#'
#' @param time_days Non-decreasing elapsed times.
#' @param cumulative_infiltration_mm Non-decreasing cumulative infiltration.
#' @param intervals Data frame with `depth_top_mm` and `depth_bottom_mm`.
#' @param mu,sigma,retardation Positive CLTF transport parameters.
#' @param decay_rate_day Global first-order degradation rate.
#' @param application_rate_g_ha Application rate in grams per hectare.
#' @param bulk_density_g_cm3 Bulk density for each interval.
#' @param effective_porosity Empirical concentration scale.
#' @return Long data frame of interval mass fractions and concentrations.
#' @export
simulate_cltf_intervals <- function(
  time_days,
  cumulative_infiltration_mm,
  intervals,
  mu,
  sigma,
  retardation,
  decay_rate_day,
  application_rate_g_ha,
  bulk_density_g_cm3,
  effective_porosity = 0.2
) {
  validate_forcing(time_days, cumulative_infiltration_mm)
  intervals <- validate_intervals(intervals)
  density <- validate_interval_density(bulk_density_g_cm3, nrow(intervals))
  validate_positive_scalar(mu, "mu")
  validate_positive_scalar(sigma, "sigma")
  validate_positive_scalar(retardation, "retardation")
  if (length(decay_rate_day) != 1L ||
      !is.finite(decay_rate_day) ||
      decay_rate_day < 0) {
    stop("decay_rate_day must be one finite non-negative value.", call. = FALSE)
  }

  probabilities <- cltf_interval_probabilities(
    cumulative_infiltration_mm,
    intervals,
    mu,
    sigma,
    retardation
  )
  remaining <- exp(-decay_rate_day * time_days)
  interval_mass <- sweep(
    probabilities[, seq_len(nrow(intervals)), drop = FALSE],
    1,
    remaining,
    `*`
  )
  below <- probabilities[, "below"] * remaining
  degraded <- 1 - remaining
  soil_masses <- vapply(
    seq_len(nrow(intervals)),
    function(index) {
      soil_mass_kg_ha(
        intervals$depth_top_mm[index],
        intervals$depth_bottom_mm[index],
        density[index]
      )
    },
    numeric(1)
  )

  rows <- vector("list", length(time_days) * nrow(intervals))
  row_index <- 1L
  for (time_index in seq_along(time_days)) {
    for (interval_index in seq_len(nrow(intervals))) {
      mass_fraction <- interval_mass[time_index, interval_index]
      rows[[row_index]] <- data.frame(
        time_days                  = time_days[time_index],
        cumulative_infiltration_mm = cumulative_infiltration_mm[time_index],
        depth_top_mm               = intervals$depth_top_mm[interval_index],
        depth_bottom_mm            = intervals$depth_bottom_mm[interval_index],
        mass_fraction              = mass_fraction,
        mass_below_profile         = below[time_index],
        mass_degraded              = degraded[time_index],
        concentration_ug_kg        = resident_concentration_ug_kg(
          application_rate_g_ha,
          mass_fraction,
          soil_masses[interval_index],
          effective_porosity
        )
      )
      row_index <- row_index + 1L
    }
  }
  do.call(rbind, rows)
}

depth_edges <- function(depths_mm) {
  if (length(depths_mm) == 0L ||
      any(!is.finite(depths_mm)) ||
      any(depths_mm < 0)) {
    stop("depths_mm must contain finite non-negative depths.", call. = FALSE)
  }
  if (length(depths_mm) == 1L) {
    width <- max(depths_mm[1], 1)
    return(c(max(0, depths_mm[1] - width / 2), depths_mm[1] + width / 2))
  }
  if (any(diff(depths_mm) <= 0)) {
    stop("depths_mm must be strictly increasing.", call. = FALSE)
  }
  midpoints <- (depths_mm[-length(depths_mm)] + depths_mm[-1]) / 2
  first <- max(0, depths_mm[1] - (depths_mm[2] - depths_mm[1]) / 2)
  last <- depths_mm[length(depths_mm)] +
    (depths_mm[length(depths_mm)] - depths_mm[length(depths_mm) - 1]) / 2
  c(first, midpoints, last)
}

spatial_density_per_mm <- function(
  cumulative_infiltration_mm,
  depths_mm,
  mu,
  sigma,
  retardation
) {
  density <- matrix(
    0,
    nrow = length(cumulative_infiltration_mm),
    ncol = length(depths_mm)
  )
  positive_time <- cumulative_infiltration_mm > 0
  positive_depth <- depths_mm > 0
  if (!any(positive_time) || !any(positive_depth)) {
    return(density)
  }

  for (time_index in which(positive_time)) {
    log_ratio <- log(
      cumulative_infiltration_mm[time_index] /
        (mu * retardation * depths_mm[positive_depth])
    )
    density[time_index, positive_depth] <-
      exp(-(log_ratio^2) / (2 * sigma^2)) /
      (depths_mm[positive_depth] * sigma * sqrt(2 * pi))
  }
  density
}

#' Simulate a continuous CLTF profile on a depth grid
#'
#' @inheritParams simulate_cltf_intervals
#' @param depths_mm Strictly increasing profile depths in millimetres.
#' @return Long data frame of point-profile concentrations.
#' @export
simulate_cltf_profile <- function(
  time_days,
  cumulative_infiltration_mm,
  depths_mm,
  mu,
  sigma,
  retardation,
  decay_rate_day,
  application_rate_g_ha,
  bulk_density_g_cm3,
  effective_porosity = 0.2
) {
  validate_forcing(time_days, cumulative_infiltration_mm)
  depths_mm <- as.numeric(depths_mm)
  if (length(depths_mm) == 0L ||
      any(!is.finite(depths_mm)) ||
      any(depths_mm < 0) ||
      any(diff(depths_mm) <= 0)) {
    stop("depths_mm must be finite, non-negative, and increasing.", call. = FALSE)
  }
  if (length(bulk_density_g_cm3) == 1L) {
    depth_density <- rep(bulk_density_g_cm3, length(depths_mm))
  } else {
    depth_density <- bulk_density_g_cm3
  }
  if (length(depth_density) != length(depths_mm) ||
      any(!is.finite(depth_density)) ||
      any(depth_density <= 0)) {
    stop("bulk_density_g_cm3 must be scalar or one value per depth.", call. = FALSE)
  }
  validate_positive_scalar(mu, "mu")
  validate_positive_scalar(sigma, "sigma")
  validate_positive_scalar(retardation, "retardation")
  if (length(decay_rate_day) != 1L ||
      !is.finite(decay_rate_day) ||
      decay_rate_day < 0) {
    stop("decay_rate_day must be one finite non-negative value.", call. = FALSE)
  }
  if (length(application_rate_g_ha) != 1L ||
      !is.finite(application_rate_g_ha) ||
      application_rate_g_ha < 0 ||
      length(effective_porosity) != 1L ||
      !is.finite(effective_porosity) ||
      effective_porosity <= 0) {
    stop("Application rate and porosity inputs are invalid.", call. = FALSE)
  }

  mass_density <- spatial_density_per_mm(
    cumulative_infiltration_mm,
    depths_mm,
    mu,
    sigma,
    retardation
  )
  mass_density <- sweep(
    mass_density,
    1,
    exp(-decay_rate_day * time_days),
    `*`
  )
  soil_mass_per_mm <- vapply(
    depth_density,
    function(value) soil_mass_kg_ha(0, 1, value),
    numeric(1)
  )
  concentration <- sweep(
    application_rate_g_ha * 1e6 * mass_density,
    2,
    soil_mass_per_mm,
    `/`
  ) * (0.2 / effective_porosity)

  rows <- vector("list", length(time_days) * length(depths_mm))
  row_index <- 1L
  for (time_index in seq_along(time_days)) {
    for (depth_index in seq_along(depths_mm)) {
      rows[[row_index]] <- data.frame(
        time_days                  = time_days[time_index],
        cumulative_infiltration_mm = cumulative_infiltration_mm[time_index],
        depth_mm                   = depths_mm[depth_index],
        mass_density_per_mm        = mass_density[time_index, depth_index],
        concentration_ug_kg        = concentration[time_index, depth_index]
      )
      row_index <- row_index + 1L
    }
  }
  do.call(rbind, rows)[
    c(
      "time_days",
      "cumulative_infiltration_mm",
      "depth_mm",
      "mass_density_per_mm",
      "concentration_ug_kg"
    )
  ]
}

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
  validate_forcing(time_days, cumulative_infiltration_mm)

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
