"""
Generate a small climate CSV from the raw BoM files in CLT_model/BoM/BCG01.
Outputs examples/data/bcg01_2019_climate.csv with columns:
Date, jdays, Tmax, Tmin, rain_mm
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    root = Path("/Users/yiyu/Library/CloudStorage/OneDrive-TheUniversityofSydney(Staff)/Work/Workspace")
    bom = root / "CLT_model/BoM/BCG01"
    rain = pd.read_csv(bom / "BCG01.csv")
    temp = pd.read_csv(bom / "BCG01TmaxTmin.csv")

    rain = rain[["Year", "Month", "Day", "Rainfall amount (millimetres)"]]
    temp = temp[["Year", "Month", "Day", "Maximum temperature (Degree C)", "Minimum temperature (Degree C)"]]

    rain = rain[rain["Year"] == 2019]
    temp = temp[temp["Year"] == 2019]

    clim = pd.merge(rain, temp, on=["Year", "Month", "Day"], how="left")
    clim["Date"] = pd.to_datetime(dict(year=clim.Year, month=clim.Month, day=clim.Day))
    clim = clim.sort_values("Date")
    clim["jdays"] = clim["Date"].dt.dayofyear
    clim.rename(
        columns={
            "Maximum temperature (Degree C)": "Tmax",
            "Minimum temperature (Degree C)": "Tmin",
            "Rainfall amount (millimetres)": "rain_mm",
        },
        inplace=True,
    )
    clim[["Tmax", "Tmin"]] = clim[["Tmax", "Tmin"]].ffill().bfill()
    clim["rain_mm"] = clim["rain_mm"].fillna(0)
    clim_out = clim[["Date", "jdays", "Tmax", "Tmin", "rain_mm"]]
    outdir = root / "GitHub/pyCLT/examples/data"
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / "bcg01_2019_climate.csv"
    clim_out.to_csv(outpath, index=False)
    print(f"Wrote {outpath} ({len(clim_out)} rows)")
    print(clim_out.head())
    print(clim_out.tail())


if __name__ == "__main__":
    main()
