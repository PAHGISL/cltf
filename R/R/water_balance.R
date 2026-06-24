# Script: water_balance.R
# Objective: Convert daily water inputs and ET into cumulative infiltration and first-passage times.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Daily rainfall, irrigation, ET, and monotone cumulative infiltration.
# Outputs: Daily infiltration, cumulative infiltration, and first-passage times.
# Usage: Use exported functions after library(rclt).
# Dependencies: base R

#' Calculate daily net infiltration
#'
#' @param rain_mm,et_mm,irrigation_mm Equal-length daily water vectors.
#' @param et_factor Non-negative multiplier applied to ET.
#' @return Daily infiltration in millimetres.
#' @export
daily_infiltration <- function(
  rain_mm,
  et_mm,
  irrigation_mm = rep(0, length(rain_mm)),
  et_factor = 1
) {
  lengths <- c(length(rain_mm), length(et_mm), length(irrigation_mm))
  if (length(unique(lengths)) != 1L) {
    stop("Water-balance vectors must have equal lengths.", call. = FALSE)
  }
  values <- c(rain_mm, et_mm, irrigation_mm, et_factor)
  if (any(!is.finite(values)) ||
      any(c(rain_mm, et_mm, irrigation_mm) < 0) ||
      length(et_factor) != 1L ||
      et_factor < 0) {
    stop("Water-balance inputs must be finite and non-negative.", call. = FALSE)
  }
  pmax(rain_mm + irrigation_mm - et_factor * et_mm, 0)
}

#' Calculate cumulative net infiltration
#'
#' @inheritParams daily_infiltration
#' @return Cumulative infiltration in millimetres.
#' @export
cumulative_infiltration <- function(
  rain_mm,
  et_mm,
  irrigation_mm = rep(0, length(rain_mm)),
  et_factor = 1
) {
  cumsum(daily_infiltration(rain_mm, et_mm, irrigation_mm, et_factor))
}

#' Find first-passage times for cumulative infiltration
#'
#' @param cumulative_infiltration_mm Finite non-decreasing infiltration.
#' @param time Equal-length finite increasing time values.
#' @param target_infiltration_mm Non-negative target infiltration levels.
#' @return First time reaching each target, or `NA_real_`.
#' @export
first_passage_time <- function(
  cumulative_infiltration_mm,
  time,
  target_infiltration_mm
) {
  if (length(cumulative_infiltration_mm) != length(time)) {
    stop(
      "Cumulative infiltration and time must have equal lengths.",
      call. = FALSE
    )
  }
  if (any(!is.finite(cumulative_infiltration_mm)) ||
      any(cumulative_infiltration_mm < 0) ||
      any(diff(cumulative_infiltration_mm) < 0)) {
    stop(
      "Cumulative infiltration must be finite and non-decreasing.",
      call. = FALSE
    )
  }
  if (any(!is.finite(time)) || any(diff(time) <= 0)) {
    stop("time must be finite and strictly increasing.", call. = FALSE)
  }
  if (any(!is.finite(target_infiltration_mm)) ||
      any(target_infiltration_mm < 0)) {
    stop("Targets must be finite and non-negative.", call. = FALSE)
  }

  vapply(
    target_infiltration_mm,
    function(target) {
      index <- which(cumulative_infiltration_mm >= target)[1]
      if (is.na(index)) {
        NA_real_
      } else {
        time[index]
      }
    },
    numeric(1)
  )
}
