"""
Minimal demo that stitches together ET, infiltration, and the CLT model.

Usage:
    python examples/synthetic_demo.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyclt.climate import calc_et
from pyclt.infiltration import cumulative_infiltration
from pyclt.model import CLTParameters, run_series


def build_synthetic_climate(days: int = 120) -> pd.DataFrame:
    """Create a toy climate dataframe with sinusoidal temperature and patchy rain."""
    dates = pd.date_range("2020-05-01", periods=days, freq="D")
    jdays = dates.dayofyear.to_numpy()
    tmax = 25 + 8 * np.sin(np.linspace(0, 3, days))
    tmin = 12 + 5 * np.sin(np.linspace(0, 3, days) - 0.3)
    rng = np.random.default_rng(42)
    rain = rng.gamma(shape=0.8, scale=8, size=days)
    rain[rng.random(days) < 0.75] = 0  # many dry days

    df = pd.DataFrame({"date": dates, "jdays": jdays, "Tmax": tmax, "Tmin": tmin, "rain_mm": rain})
    df["et0_mm"] = calc_et(latitude_deg=-35.9, data=df)
    return df


def main() -> None:
    climate = build_synthetic_climate()
    infil = cumulative_infiltration(climate["rain_mm"].to_numpy(), climate["et0_mm"].to_numpy(), et_factor=1.0)
    times = np.arange(len(infil), dtype=float)

    params = CLTParameters(
        mu=3.0,
        sigma=1.0,
        effective_porosity=0.2,
        retardation_top=6.0,
        decay_top=0.0015,
        reference_depth=100.0,
        retardation_bottom=6.0,
        decay_bottom=0.02,
        min_value=0.0001,
    )
    top, bottom = run_series(times, infil, params)

    summary = pd.DataFrame(
        {
            "date": climate["date"],
            "rain_mm": climate["rain_mm"],
            "et0_mm": climate["et0_mm"],
            "cumulative_infiltration_mm": infil,
            "top_relative_conc": top,
            "subsoil_relative_conc": bottom,
        }
    )
    print(summary.head(10))
    print("\n... tail ...\n")
    print(summary.tail(5))

    # Plotting omitted by default to keep the demo fast and headless-friendly.


if __name__ == "__main__":
    main()
