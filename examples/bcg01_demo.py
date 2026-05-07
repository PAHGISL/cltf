"""
Demo using BoM-derived climate data (BCG01, year 2019) produced by generate_bcg01_climate.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

# Use non-interactive backend for headless environments.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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

    # Persist tabular results
    out_csv = ROOT / "examples" / "data" / "bcg01_results.csv"
    df[["Date", "rain_mm", "et0_mm", "cumulative_infiltration_mm", "top_rel_conc", "subsoil_rel_conc"]].to_csv(
        out_csv, index=False
    )

    # Plot time series for top/subsoil relative concentration
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df["Date"], df["top_rel_conc"], label="0–10 cm (relative)", color="tab:blue")
    ax.plot(df["Date"], df["subsoil_rel_conc"], label="10–30 cm (relative)", color="tab:orange")
    ax.set_ylabel("Relative concentration (C/C0)")
    ax.set_xlabel("Date")
    ax.legend()
    fig.autofmt_xdate()
    plt.tight_layout()
    out_png = ROOT / "examples" / "data" / "bcg01_results.png"
    fig.savefig(out_png, dpi=150)

    print("Wrote results:")
    print(f" - {out_csv}")
    print(f" - {out_png}")
    print(df[["Date", "rain_mm", "et0_mm", "cumulative_infiltration_mm", "top_rel_conc", "subsoil_rel_conc"]].head())
    print("\n... tail ...\n")
    print(df[["Date", "rain_mm", "et0_mm", "cumulative_infiltration_mm", "top_rel_conc", "subsoil_rel_conc"]].tail())


if __name__ == "__main__":
    main()
