"""
Demo using BoM-derived climate data (BCG01, year 2019) produced by generate_bcg01_climate.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyclt.climate import calc_et
from pyclt.infiltration import cumulative_infiltration
from pyclt.model import CLTParameters, run_series


def main() -> None:
    data_path = ROOT / "examples" / "data" / "bcg01_2019_climate.csv"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing dataset at {data_path}. Run examples/generate_bcg01_climate.py first.")

    df = pd.read_csv(data_path, parse_dates=["Date"])
    df["et0_mm"] = calc_et(latitude_deg=-35.9, data=df)
    df["cumulative_infiltration_mm"] = cumulative_infiltration(df["rain_mm"], df["et0_mm"], et_factor=1.0)
    times = np.arange(len(df), dtype=float)

    params = CLTParameters(
        mu=3.0,
        sigma=1.0,
        effective_porosity=0.2,
        retardation_top=6.0,
        decay_top=0.0015,
        reference_depth=100.0,
        retardation_bottom=8.0,
        decay_bottom=0.02,
        min_value=0.0001,
    )
    top, bottom = run_series(times, df["cumulative_infiltration_mm"], params)
    df["top_rel_conc"] = top
    df["subsoil_rel_conc"] = bottom

    print(df[["Date", "rain_mm", "et0_mm", "cumulative_infiltration_mm", "top_rel_conc", "subsoil_rel_conc"]].head())
    print("\n... tail ...\n")
    print(df[["Date", "rain_mm", "et0_mm", "cumulative_infiltration_mm", "top_rel_conc", "subsoil_rel_conc"]].tail())


if __name__ == "__main__":
    main()
