"""
Climate and radiation utilities translated from the R implementation.
Formulas follow Priestley–Taylor PET using daily max/min temperature only.
"""

from __future__ import annotations

import math
from typing import Iterable, Literal, Sequence

import numpy as np
import pandas as pd

# Constants
PI = math.pi
LATENT_HEAT_EVAP = 2500.0  # kJ/kg
DENSITY_WATER = 1000.0  # kg/m3
PSYCHROMETRIC_CONST = 0.066  # kPa/K
SB_CONSTANT = 0.00000490  # kJ m-2 K-4 d-1


def declination(jday: np.ndarray) -> np.ndarray:
    """Solar declination (radians) for day of year."""
    return 0.4102 * np.sin(PI * (jday - 80) / 180.0)


def solar_angle(latitude: float, jday: np.ndarray) -> np.ndarray:
    """Solar inclination angle from horizontal at solar noon (radians)."""
    dec = declination(jday)
    return np.arcsin(np.sin(latitude) * np.sin(dec) + np.cos(latitude) * np.cos(dec))


def slope_factor(latitude: float, jday: np.ndarray, slope: float, aspect: float) -> np.ndarray:
    """
    Adjust solar radiation for land slope/aspect.
    Returns factor relative to level ground (1 == flat).
    """
    solar_aspect = np.where(latitude - declination(jday) < 0, 0.0, PI)
    with np.errstate(divide="ignore", invalid="ignore"):
        sf = np.cos(slope) - np.sin(slope) * np.cos(aspect - (PI - solar_aspect)) / solar_angle(latitude, jday)
    sf[sf < 0] = 0
    return sf


def potential_solar(latitude: float, jday: np.ndarray) -> np.ndarray:
    """Potential solar radiation at the edge of the atmosphere [kJ m-2 d-1]."""
    dec = declination(jday)
    return (
        117500
        * (
            (np.arccos(-np.tan(dec) * np.tan(latitude)) * np.sin(latitude) * np.sin(dec))
            + (np.cos(latitude) * np.cos(dec) * np.sin(np.arccos(np.tan(dec) * np.tan(latitude))))
        )
        / PI
    )


def transmissivity(
    tmax: Sequence[float],
    tmin: Sequence[float],
    A: float = 0.75,
    C: float = 2.4,
    opt: Literal["1day", "2day"] = "1day",
) -> np.ndarray:
    """
    Bristow–Campbell atmospheric transmissivity from diurnal temperature range.
    Mirrors the R routine; smoothing matches the original sliding-window logic.
    """
    tmax_arr = np.asarray(tmax, dtype=float)
    tmin_arr = np.asarray(tmin, dtype=float)
    if (tmax_arr < tmin_arr).any():
        raise ValueError("tmax contains values below tmin; check inputs.")

    dT = tmax_arr - tmin_arr
    length = len(dT)
    av_delta_t = np.empty_like(dT)

    if opt == "2day" and length > 1:
        for i in range(length - 1):
            dT[i] = tmax_arr[i] - (tmin_arr[i] + tmin_arr[i + 1]) / 2.0

    if length < 30:
        av_delta_t[:] = dT.mean()
    else:
        av_delta_t[:14] = dT[:30].mean()
        av_delta_t[length - 14 :] = dT[length - 30 :].mean()
        for i in range(14, length - 14):
            av_delta_t[i] = dT[i - 14 : i + 15].mean()

    B = 0.036 * np.exp(-0.154 * av_delta_t)
    return A * (1 - np.exp(-B * np.power(dT, C)))


def est_cloudiness(
    tmax: Sequence[float],
    tmin: Sequence[float],
    trans: np.ndarray | None = None,
    trans_min: float = 0.15,
    trans_max: float = 0.75,
    opt: Literal["linear", "Black"] = "linear",
) -> np.ndarray:
    """Estimate daily cloudiness fraction from transmissivity."""
    if trans is None:
        trans = transmissivity(tmax, tmin)
    if opt == "Black":
        cl = (0.34 - np.sqrt(0.34**2 + 4 * 0.458 * (0.803 - trans))) / (-2 * 0.458)
        cl[trans > 0.803] = 0
    else:
        cl = 1 - (trans - trans_min) / (trans_max - trans_min)
    cl = np.clip(cl, 0, 1)
    return cl


def atmospheric_emissivity(
    airtemp: np.ndarray,
    cloudiness: np.ndarray,
    vapour_pressure_kpa: np.ndarray | None = None,
    opt: Literal["linear", "Brutsaert"] = "linear",
) -> np.ndarray:
    """Sky emissivity following R helper."""
    if opt == "Brutsaert":
        if vapour_pressure_kpa is None:
            raise ValueError("vapour_pressure_kpa required for Brutsaert option")
        return (1.24 * ((vapour_pressure_kpa * 10) / (airtemp + 273.2)) ** (1 / 7)) * (
            1 - 0.84 * cloudiness
        ) + 0.84 * cloudiness
    return (0.72 + 0.005 * airtemp) * (1 - 0.84 * cloudiness) + 0.84 * cloudiness


def longwave(emissivity: np.ndarray, temperature_c: np.ndarray) -> np.ndarray:
    """Daily longwave radiation (kJ m-2 d-1)."""
    temp_k = temperature_c + 273.15
    return emissivity * SB_CONSTANT * np.power(temp_k, 4)


def solar_radiation(
    latitude: float,
    jday: np.ndarray,
    tmax: np.ndarray,
    tmin: np.ndarray,
    albedo: float = 0.2,
    forest: float = 0.0,
    slope: float = 0.0,
    aspect: float = 0.0,
    units: Literal["kJm2d", "Wm2"] = "kJm2d",
) -> np.ndarray:
    """Net shortwave radiation absorbed at the surface."""
    convert = 1 if units == "kJm2d" else 86.4
    return (
        (1 - albedo)
        * (1 - forest)
        * transmissivity(tmax, tmin)
        * potential_solar(latitude, jday)
        * slope_factor(latitude, jday, slope, aspect)
        / convert
    )


def net_radiation(
    latitude: float,
    jday: np.ndarray,
    tmax: np.ndarray,
    tmin: np.ndarray,
    albedo: float = 0.18,
    forest: float = 0.0,
    slope: float = 0.0,
    aspect: float = 0.0,
    airtemp: np.ndarray | None = None,
    cloudiness: np.ndarray | Literal["Estimate"] = "Estimate",
    surf_emissivity: float = 0.97,
    surf_temp: np.ndarray | None = None,
    units: Literal["kJm2d", "Wm2"] = "kJm2d",
    vapour_pressure_kpa: np.ndarray | None = None,
    emissivity_opt: Literal["linear", "Brutsaert"] = "linear",
) -> np.ndarray:
    """Net radiation (shortwave + longwave) at the surface."""
    if airtemp is None:
        airtemp = (np.asarray(tmax) + np.asarray(tmin)) / 2.0
    if surf_temp is None:
        surf_temp = airtemp
    if isinstance(cloudiness, str) and cloudiness == "Estimate":
        cloudiness = est_cloudiness(tmax, tmin)
    if units == "kJm2d":
        convert = 1
    else:
        convert = 86.4

    sw = solar_radiation(latitude, jday, tmax, tmin, albedo, forest, slope, aspect, units="kJm2d")
    atm_emiss = atmospheric_emissivity(np.asarray(airtemp), np.asarray(cloudiness), vapour_pressure_kpa, emissivity_opt)
    lw_in = longwave(atm_emiss, np.asarray(airtemp))
    lw_out = longwave(surf_emissivity, np.asarray(surf_temp))
    return (sw + lw_in - lw_out) / convert


def sat_vap_pressure_slope(temp_c: np.ndarray) -> np.ndarray:
    return (2508.3 / np.power(temp_c + 237.3, 2)) * np.exp(17.3 * temp_c / (temp_c + 237.3))


def pt_pet(net_rad: np.ndarray, temp_c: np.ndarray, pt_constant: float = 1.26) -> np.ndarray:
    """Priestley–Taylor PET [m/day] given net radiation (kJ/m2/d) and temperature."""
    pet = (
        pt_constant
        * sat_vap_pressure_slope(temp_c)
        * net_rad
        / ((sat_vap_pressure_slope(temp_c) + PSYCHROMETRIC_CONST) * (LATENT_HEAT_EVAP * DENSITY_WATER))
    )
    pet[pet < 0] = 0
    return np.round(pet, 4)


def pet_from_temp(
    jday: Iterable[int],
    tmax_c: Iterable[float],
    tmin_c: Iterable[float],
    lat_degrees: float,
    albedo: float = 0.18,
    surface_emissivity: float = 0.97,
    aspect: float = 0.0,
    slope: float = 0.0,
    forest: float = 0.0,
    pt_constant: float = 1.26,
    emissivity_opt: Literal["linear", "Brutsaert"] = "linear",
    vapour_pressure_kpa: Iterable[float] | None = None,
) -> np.ndarray:
    """
    Priestley–Taylor PET from Tmax/Tmin.
    Returns PET in metres/day (multiply by 1000 for mm/day).
    """
    jday_arr = np.asarray(jday, dtype=float)
    tmax_arr = np.asarray(tmax_c, dtype=float)
    tmin_arr = np.asarray(tmin_c, dtype=float)
    if not (len(jday_arr) == len(tmax_arr) == len(tmin_arr)):
        raise ValueError("Input arrays must share length.")
    avg_t = (tmax_arr + tmin_arr) / 2.0
    rad = net_radiation(
        lat_degrees * PI / 180.0,
        jday_arr,
        tmax_arr,
        tmin_arr,
        albedo=albedo,
        forest=forest,
        slope=slope,
        aspect=aspect,
        airtemp=avg_t,
        cloudiness="Estimate",
        surf_emissivity=surface_emissivity,
        surf_temp=avg_t,
        vapour_pressure_kpa=None if vapour_pressure_kpa is None else np.asarray(vapour_pressure_kpa),
        emissivity_opt=emissivity_opt,
    )
    pet = pt_pet(rad, avg_t, pt_constant)
    pet[tmax_arr == -999] = -999
    pet[tmin_arr == -999] = -999
    return pet


def calc_et(latitude_deg: float, data: pd.DataFrame) -> np.ndarray:
    """
    Convenience wrapper for daily ET0 in mm/day.
    Expects columns jdays, Tmax, Tmin in the dataframe.
    """
    required = {"jdays", "Tmax", "Tmin"}
    missing = required - set(data.columns)
    if missing:
        raise KeyError(f"Missing columns for ET calculation: {', '.join(sorted(missing))}")
    pet_m = pet_from_temp(
        jday=data["jdays"].to_numpy(),
        tmax_c=data["Tmax"].to_numpy(),
        tmin_c=data["Tmin"].to_numpy(),
        lat_degrees=latitude_deg,
    )
    return pet_m * 1000.0
