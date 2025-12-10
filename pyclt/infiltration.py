"""Simple soil water balance helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def cumulative_infiltration(
    rainfall_mm: np.ndarray,
    et_mm: np.ndarray,
    et_factor: float = 1.0,
) -> np.ndarray:
    """
    Cumulative net infiltration following the R `cuminfilt` helper.
    Daily infiltration = max(rain - et_factor * ET0, 0).
    """
    rainfall = np.asarray(rainfall_mm, dtype=float)
    et = np.asarray(et_mm, dtype=float) * et_factor
    daily = np.where(rainfall > et, rainfall - et, 0.0)
    return np.cumsum(daily)


def cumulative_infiltration_from_df(
    df: pd.DataFrame,
    rain_col: str = "rain_mm",
    et_col: str = "et0_mm",
    et_factor: float = 1.0,
) -> np.ndarray:
    """DataFrame-friendly wrapper around `cumulative_infiltration`."""
    if rain_col not in df or et_col not in df:
        raise KeyError(f"DataFrame must include '{rain_col}' and '{et_col}'")
    return cumulative_infiltration(df[rain_col].to_numpy(), df[et_col].to_numpy(), et_factor)
