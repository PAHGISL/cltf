#!/usr/bin/env python3
"""
Script: climate.py
Objective: Calculate temperature-based Priestley-Taylor PET for CLTF forcing.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Day-of-year, daily temperatures, latitude, and radiation parameters.
Outputs: Potential evapotranspiration in millimetres per day.
Usage: Import pet_from_temperature from cltf or cltf.climate.
Dependencies: math, numpy
"""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import ArrayLike


def _solar_declination(jday: np.ndarray) -> np.ndarray:
    return 0.4102 * np.sin(np.pi * (jday - 80.0) / 180.0)


def _solar_angle(latitude: float, jday: np.ndarray) -> np.ndarray:
    declination = _solar_declination(jday)
    return np.arcsin(
        np.sin(latitude) * np.sin(declination)
        + np.cos(latitude) * np.cos(declination)
    )


def _slope_factor(
    latitude: float,
    jday: np.ndarray,
    slope: float,
    aspect: float,
) -> np.ndarray:
    solar_aspect = np.where(
        latitude - _solar_declination(jday) < 0,
        0.0,
        np.pi,
    )
    result = np.cos(slope) - (
        np.sin(slope)
        * np.cos(aspect - (np.pi - solar_aspect))
        / _solar_angle(latitude, jday)
    )
    return np.maximum(result, 0.0)


def _potential_solar(latitude: float, jday: np.ndarray) -> np.ndarray:
    declination = _solar_declination(jday)
    return 117500.0 * (
        np.arccos(-np.tan(declination) * np.tan(latitude))
        * np.sin(latitude)
        * np.sin(declination)
        + np.cos(latitude)
        * np.cos(declination)
        * np.sin(np.arccos(np.tan(declination) * np.tan(latitude)))
    ) / np.pi


def _temperature_transmissivity(
    tmax_c: np.ndarray,
    tmin_c: np.ndarray,
) -> np.ndarray:
    delta_t = tmax_c - tmin_c
    n_values = len(delta_t)
    average_delta_t = np.empty(n_values, dtype=float)

    if n_values < 30:
        average_delta_t.fill(np.mean(delta_t))
    else:
        average_delta_t[:14] = np.mean(delta_t[:30])
        average_delta_t[-14:] = np.mean(delta_t[-30:])
        for index in range(14, n_values - 14):
            average_delta_t[index] = np.mean(
                delta_t[index - 14:index + 15]
            )

    coefficient_b = 0.036 * np.exp(-0.154 * average_delta_t)
    return 0.75 * (1.0 - np.exp(-coefficient_b * delta_t**2.4))


def _estimated_cloudiness(transmissivity: np.ndarray) -> np.ndarray:
    return np.clip(1.0 - (transmissivity - 0.15) / (0.75 - 0.15), 0.0, 1.0)


def _atmospheric_emissivity(
    air_temperature_c: np.ndarray,
    cloudiness: np.ndarray,
) -> np.ndarray:
    return (
        (0.72 + 0.005 * air_temperature_c) * (1.0 - 0.84 * cloudiness)
        + 0.84 * cloudiness
    )


def _longwave_radiation(
    emissivity: float | np.ndarray,
    temperature_c: np.ndarray,
) -> np.ndarray:
    return emissivity * 0.00000490 * (temperature_c + 273.15) ** 4


def _saturation_vapour_pressure_slope(
    temperature_c: np.ndarray,
) -> np.ndarray:
    return (
        2508.3
        / (temperature_c + 237.3) ** 2
        * np.exp(17.3 * temperature_c / (temperature_c + 237.3))
    )


def pet_from_temperature(
    jday: ArrayLike,
    tmax_c: ArrayLike,
    tmin_c: ArrayLike,
    latitude_deg: float,
    albedo: float = 0.18,
    surface_emissivity: float = 0.97,
    aspect: float = 0.0,
    slope: float = 0.0,
    forest: float = 0.0,
    pt_constant: float = 1.26,
) -> np.ndarray:
    """Calculate daily Priestley-Taylor PET from maximum/minimum temperature."""

    day = np.atleast_1d(np.asarray(jday, dtype=float))
    maximum = np.atleast_1d(np.asarray(tmax_c, dtype=float))
    minimum = np.atleast_1d(np.asarray(tmin_c, dtype=float))
    if len({len(day), len(maximum), len(minimum)}) != 1 or len(day) == 0:
        raise ValueError(
            "Temperature and day-of-year vectors must have equal lengths"
        )

    scalar_values = (
        latitude_deg,
        albedo,
        surface_emissivity,
        aspect,
        slope,
        forest,
        pt_constant,
    )
    if (
        not np.all(np.isfinite(day))
        or not np.all(np.isfinite(maximum))
        or not np.all(np.isfinite(minimum))
        or not all(math.isfinite(value) for value in scalar_values)
    ):
        raise ValueError("PET inputs must be finite")
    if np.any(maximum < minimum):
        raise ValueError(
            "Maximum temperature contains values below minimum temperature"
        )

    latitude = latitude_deg * np.pi / 180.0
    average_temperature = (maximum + minimum) / 2.0
    transmissivity = _temperature_transmissivity(maximum, minimum)
    cloudiness = _estimated_cloudiness(transmissivity)
    shortwave = (
        (1.0 - albedo)
        * (1.0 - forest)
        * transmissivity
        * _potential_solar(latitude, day)
        * _slope_factor(latitude, day, slope, aspect)
    )
    longwave_in = _longwave_radiation(
        _atmospheric_emissivity(average_temperature, cloudiness),
        average_temperature,
    )
    longwave_out = _longwave_radiation(
        surface_emissivity,
        average_temperature,
    )
    net_radiation = shortwave + longwave_in - longwave_out
    vapour_slope = _saturation_vapour_pressure_slope(average_temperature)
    pet_m_day = (
        pt_constant
        * vapour_slope
        * net_radiation
        / ((vapour_slope + 0.066) * (2500.0 * 1000.0))
    )
    return np.round(np.maximum(pet_m_day, 0.0), 4) * 1000.0
