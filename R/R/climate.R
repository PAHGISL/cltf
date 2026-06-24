# Script: climate.R
# Objective: Calculate temperature-based Priestley-Taylor PET for CLTF forcing.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Day-of-year, daily temperature, latitude, and radiation parameters.
# Outputs: Potential evapotranspiration in millimetres per day.
# Usage: Use pet_from_temperature() after library(cltf).
# Dependencies: base R

solar_declination <- function(jday) {
  0.4102 * sin(pi * (jday - 80) / 180)
}

solar_angle <- function(latitude, jday) {
  declination <- solar_declination(jday)
  asin(
    sin(latitude) * sin(declination) +
      cos(latitude) * cos(declination)
  )
}

slope_factor <- function(latitude, jday, slope, aspect) {
  solar_aspect <- ifelse(latitude - solar_declination(jday) < 0, 0, pi)
  result <- cos(slope) -
    sin(slope) * cos(aspect - (pi - solar_aspect)) /
      solar_angle(latitude, jday)
  pmax(result, 0)
}

potential_solar <- function(latitude, jday) {
  declination <- solar_declination(jday)
  117500 * (
    acos(-tan(declination) * tan(latitude)) *
      sin(latitude) * sin(declination) +
      cos(latitude) * cos(declination) *
        sin(acos(tan(declination) * tan(latitude)))
  ) / pi
}

temperature_transmissivity <- function(tmax_c, tmin_c) {
  delta_t <- tmax_c - tmin_c
  n <- length(delta_t)
  average_delta_t <- numeric(n)

  if (n < 30L) {
    average_delta_t[] <- mean(delta_t)
  } else {
    average_delta_t[seq_len(14)] <- mean(delta_t[seq_len(30)])
    average_delta_t[(n - 13):n] <- mean(delta_t[(n - 29):n])
    for (index in 15:(n - 14)) {
      average_delta_t[index] <- mean(
        delta_t[(index - 14):(index + 14)]
      )
    }
  }

  coefficient_b <- 0.036 * exp(-0.154 * average_delta_t)
  0.75 * (1 - exp(-coefficient_b * delta_t^2.4))
}

estimated_cloudiness <- function(transmissivity) {
  pmin(pmax(1 - (transmissivity - 0.15) / (0.75 - 0.15), 0), 1)
}

atmospheric_emissivity <- function(air_temperature_c, cloudiness) {
  (0.72 + 0.005 * air_temperature_c) * (1 - 0.84 * cloudiness) +
    0.84 * cloudiness
}

longwave_radiation <- function(emissivity, temperature_c) {
  emissivity * 0.00000490 * (temperature_c + 273.15)^4
}

saturation_vapour_pressure_slope <- function(temperature_c) {
  (2508.3 / (temperature_c + 237.3)^2) *
    exp(17.3 * temperature_c / (temperature_c + 237.3))
}

#' Calculate Priestley-Taylor PET from daily temperatures
#'
#' @param jday Day-of-year values.
#' @param tmax_c,tmin_c Daily maximum and minimum temperatures in degrees Celsius.
#' @param latitude_deg Latitude in decimal degrees.
#' @param albedo Surface albedo.
#' @param surface_emissivity Surface emissivity.
#' @param aspect,slope Surface aspect and slope in radians.
#' @param forest Fractional forest cover.
#' @param pt_constant Priestley-Taylor coefficient.
#' @return Potential evapotranspiration in millimetres per day.
#' @export
pet_from_temperature <- function(
  jday,
  tmax_c,
  tmin_c,
  latitude_deg,
  albedo             = 0.18,
  surface_emissivity = 0.97,
  aspect             = 0,
  slope              = 0,
  forest             = 0,
  pt_constant        = 1.26
) {
  lengths <- c(length(jday), length(tmax_c), length(tmin_c))
  if (length(unique(lengths)) != 1L || lengths[1] == 0L) {
    stop("Temperature and day-of-year vectors must have equal lengths.", call. = FALSE)
  }
  values <- c(
    jday,
    tmax_c,
    tmin_c,
    latitude_deg,
    albedo,
    surface_emissivity,
    aspect,
    slope,
    forest,
    pt_constant
  )
  if (any(!is.finite(values))) {
    stop("PET inputs must be finite.", call. = FALSE)
  }
  if (any(tmax_c < tmin_c)) {
    stop("Maximum temperature contains values below minimum temperature.", call. = FALSE)
  }

  latitude <- latitude_deg * pi / 180
  average_temperature <- (tmax_c + tmin_c) / 2
  transmissivity <- temperature_transmissivity(tmax_c, tmin_c)
  cloudiness <- estimated_cloudiness(transmissivity)
  shortwave <- (1 - albedo) * (1 - forest) * transmissivity *
    potential_solar(latitude, jday) *
    slope_factor(latitude, jday, slope, aspect)
  longwave_in <- longwave_radiation(
    atmospheric_emissivity(average_temperature, cloudiness),
    average_temperature
  )
  longwave_out <- longwave_radiation(
    surface_emissivity,
    average_temperature
  )
  net_radiation <- shortwave + longwave_in - longwave_out
  vapour_slope <- saturation_vapour_pressure_slope(average_temperature)
  pet_m_day <- pt_constant * vapour_slope * net_radiation /
    ((vapour_slope + 0.066) * (2500 * 1000))
  round(pmax(pet_m_day, 0), 4) * 1000
}
