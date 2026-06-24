#!/usr/bin/env python3
"""
Script: observations.py
Objective: Prepare replicate-level herbicide observations for CLTF analysis.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Herbicide workbooks or tidy concentration vectors.
Outputs: Depth intervals, non-detect fields, summaries, and applied mass.
Usage: Import public functions from cltf or cltf.observations.
Dependencies: math, pathlib, numpy, pandas, cltf.concentration
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from .concentration import soil_mass_kg_ha


_DEPTH_INTERVALS = {
    "SA:10cm": (0.0, 100.0),
    "SA:30cm": (100.0, 300.0),
    "NSW:15cm": (0.0, 150.0),
    "NSW:30cm": (150.0, 300.0),
    "QLD:10cm": (0.0, 100.0),
    "QLD:30cm": (100.0, 300.0),
}

_SITE_IDS = {
    "SA": "SA_Minnipa",
    "NSW": "NSW_Griffith",
    "QLD": "QLD_Wellcamp",
}

_IDENTIFIER_COLUMNS = (
    "Soil",
    "Irrigation",
    "Timepoint",
    "Crop_2024",
    "Depth",
    "Sample_date",
)


def depth_interval_mm(sheet: str, depth_label: str) -> tuple[float, float]:
    """Map a workbook jurisdiction/depth label to an explicit interval."""

    normalized_depth = "".join(str(depth_label).strip().lower().split())
    key = f"{str(sheet).strip().upper()}:{normalized_depth}"
    try:
        return _DEPTH_INTERVALS[key]
    except KeyError as error:
        raise ValueError(
            f"Unsupported sheet/depth combination: {key}"
        ) from error


def prepare_non_detects(
    concentration_ug_kg: ArrayLike,
    is_non_detect: ArrayLike,
    detection_limit_ug_kg: ArrayLike,
) -> pd.DataFrame:
    """Prepare analysis concentrations with explicit detection-limit handling."""

    concentration = np.atleast_1d(
        np.asarray(concentration_ug_kg, dtype=float)
    )
    non_detect_raw = np.atleast_1d(np.asarray(is_non_detect, dtype=object))
    detection_limit = np.atleast_1d(
        np.asarray(detection_limit_ug_kg, dtype=float)
    )
    if len({len(concentration), len(non_detect_raw), len(detection_limit)}) != 1:
        raise ValueError("Non-detect input vectors must have equal lengths")
    if not np.all(np.isfinite(concentration)):
        raise ValueError("Reported concentrations must be finite")
    if pd.isna(non_detect_raw).any():
        raise ValueError("is_non_detect cannot contain missing values")

    non_detect = non_detect_raw.astype(bool)
    substituted = (
        non_detect
        & np.isfinite(detection_limit)
        & (detection_limit > 0)
    )
    excluded_zero = (concentration <= 0) & ~substituted
    analysis = concentration.copy()
    analysis[substituted] = detection_limit[substituted] / 2.0
    analysis[excluded_zero] = np.nan

    return pd.DataFrame(
        {
            "analysis_concentration_ug_kg": analysis,
            "lod_substituted": substituted,
            "excluded_zero": excluded_zero,
        }
    )


def geometric_concentration(
    data: pd.DataFrame,
    group_columns: Sequence[str],
) -> pd.DataFrame:
    """Calculate grouped geometric means and geometric standard deviations."""

    concentration_column = "analysis_concentration_ug_kg"
    if concentration_column not in data.columns:
        raise ValueError(
            f"data must contain {concentration_column}"
        )
    groups = list(group_columns)
    if not groups or not set(groups).issubset(data.columns):
        raise ValueError("group_columns must identify columns in data")

    rows: list[dict[str, object]] = []
    grouper: str | list[str] = groups[0] if len(groups) == 1 else groups
    grouped = data.groupby(grouper, sort=True, dropna=True, observed=True)
    for key, group in grouped:
        keys = key if isinstance(key, tuple) else (key,)
        values = pd.to_numeric(
            group[concentration_column],
            errors="coerce",
        ).to_numpy(dtype=float)
        values = values[np.isfinite(values) & (values > 0)]
        log_values = np.log(values)
        row = dict(zip(groups, keys))
        row["n"] = len(values)
        row["geometric_mean_ug_kg"] = (
            float(np.exp(np.mean(log_values))) if len(values) else np.nan
        )
        row["geometric_sd"] = (
            float(np.exp(np.std(log_values, ddof=1)))
            if len(values) > 1
            else np.nan
        )
        rows.append(row)

    return pd.DataFrame(
        rows,
        columns=groups + ["n", "geometric_mean_ug_kg", "geometric_sd"],
    )


def _normalize_sample_date(values: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_datetime(
            values,
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        ).dt.normalize()
    return pd.to_datetime(values, errors="coerce").dt.normalize()


def _text_column(
    data: pd.DataFrame,
    column: str,
    default: object,
) -> pd.Series:
    values = (
        data[column]
        if column in data.columns
        else pd.Series(default, index=data.index)
    )
    return values.astype("string").str.strip()


def _prepare_workbook_sheet(path: Path, sheet: str) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet)
    missing = {
        "Soil",
        "Timepoint",
        "Depth",
        "Sample_date",
    }.difference(raw.columns)
    if missing:
        raise ValueError(
            f"Sheet {sheet} is missing required columns: {sorted(missing)}"
        )

    sheet_key = sheet.upper()
    try:
        site_id = _SITE_IDS[sheet_key]
    except KeyError as error:
        raise ValueError(f"Unsupported workbook sheet: {sheet}") from error

    herbicide_columns = [
        column
        for column in raw.columns
        if column not in _IDENTIFIER_COLUMNS
    ]
    frames: list[pd.DataFrame] = []
    for herbicide in herbicide_columns:
        concentration = pd.to_numeric(raw[herbicide], errors="coerce")
        keep = np.isfinite(concentration.to_numpy(dtype=float))
        if not np.any(keep):
            continue

        selected = raw.loc[keep]
        frames.append(
            pd.DataFrame(
                {
                    "site_id": site_id,
                    "source_sheet": sheet,
                    "source_row": selected.index.to_numpy(dtype=int) + 2,
                    "soil_group": _text_column(raw, "Soil", pd.NA).loc[keep],
                    "treatment": _text_column(
                        raw,
                        "Irrigation",
                        "All",
                    ).loc[keep],
                    "crop_2024": _text_column(
                        raw,
                        "Crop_2024",
                        pd.NA,
                    ).loc[keep],
                    "timepoint": _text_column(
                        raw,
                        "Timepoint",
                        pd.NA,
                    ).loc[keep],
                    "depth_label": _text_column(
                        raw,
                        "Depth",
                        pd.NA,
                    ).loc[keep],
                    "sample_date": _normalize_sample_date(
                        raw["Sample_date"]
                    ).loc[keep],
                    "herbicide": str(herbicide),
                    "concentration_ug_kg": concentration.loc[keep],
                }
            ).reset_index(drop=True)
        )

    if not frames:
        raise ValueError(f"No herbicide concentrations found in sheet {sheet}")
    return pd.concat(frames, ignore_index=True)


def read_herbicide_workbook(
    path: str | Path,
    sheets: Sequence[str] = ("SA", "NSW", "Qld"),
) -> pd.DataFrame:
    """Read and normalize the herbicide dissipation workbook."""

    workbook_path = Path(path)
    if not workbook_path.exists():
        raise FileNotFoundError(
            f"Observation workbook does not exist: {workbook_path}"
        )

    observations = pd.concat(
        [
            _prepare_workbook_sheet(workbook_path, sheet)
            for sheet in sheets
        ],
        ignore_index=True,
    )
    intervals = [
        depth_interval_mm(sheet, depth)
        for sheet, depth in zip(
            observations["source_sheet"],
            observations["depth_label"],
        )
    ]
    observations["depth_top_mm"] = [interval[0] for interval in intervals]
    observations["depth_bottom_mm"] = [
        interval[1] for interval in intervals
    ]
    observations["is_t0"] = observations["timepoint"].str.upper().eq("T0")

    application_keys = ["site_id", "soil_group", "treatment"]
    application_dates = (
        observations.loc[observations["is_t0"]]
        .groupby(application_keys, sort=True, dropna=False)["sample_date"]
        .min()
        .rename("application_date")
    )
    observations = observations.join(application_dates, on=application_keys)
    if observations["application_date"].isna().any():
        raise ValueError(
            "At least one observation group has no T0 application date"
        )
    observations["days_since_application"] = (
        observations["sample_date"] - observations["application_date"]
    ).dt.days.astype(int)

    replicate_keys = [
        "site_id",
        "soil_group",
        "treatment",
        "herbicide",
        "depth_top_mm",
        "depth_bottom_mm",
        "sample_date",
    ]
    observations["replicate_id"] = (
        observations.groupby(
            replicate_keys,
            sort=True,
            dropna=False,
        ).cumcount()
        + 1
    )
    observations["is_non_detect"] = False
    observations["detection_limit_ug_kg"] = np.nan
    observations["is_zero_reported"] = (
        observations["concentration_ug_kg"] <= 0
    )
    non_detects = prepare_non_detects(
        observations["concentration_ug_kg"],
        observations["is_non_detect"],
        observations["detection_limit_ug_kg"],
    )
    observations = pd.concat(
        [observations.reset_index(drop=True), non_detects],
        axis=1,
    )
    observations["unit_status"] = "inferred_from_application_rate"

    sort_columns = [
        "site_id",
        "soil_group",
        "treatment",
        "herbicide",
        "sample_date",
        "depth_top_mm",
        "replicate_id",
    ]
    return observations.sort_values(
        sort_columns,
        kind="stable",
    ).reset_index(drop=True)


def infer_application_rate_g_ha(
    t0_concentration_ug_kg: ArrayLike,
    depth_top_mm: float,
    depth_bottom_mm: float,
    bulk_density_g_cm3: float,
) -> float:
    """Infer applied mass from positive top-layer T0 concentrations."""

    concentration = np.atleast_1d(
        np.asarray(t0_concentration_ug_kg, dtype=float)
    )
    if (
        len(concentration) == 0
        or not np.all(np.isfinite(concentration))
        or np.any(concentration <= 0)
    ):
        raise ValueError(
            "T0 concentrations must be finite and greater than zero"
        )
    soil_mass = soil_mass_kg_ha(
        depth_top_mm,
        depth_bottom_mm,
        bulk_density_g_cm3,
    )
    return float(math.exp(np.mean(np.log(concentration))) * soil_mass / 1e6)
