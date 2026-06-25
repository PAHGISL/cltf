#!/usr/bin/env python3
"""
Script: validation.py
Objective: Validate uploaded resident-concentration observation CSVs.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: Observation CSV data frames and selected shared site records.
Outputs: Prepared replicate-level CLTF observation tables.
Usage: Call prepare_uploaded_observations() before CLTF app runs.
Dependencies: dataclasses, numpy, pandas, cltf, workbench
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from workbench.config import ensure_cltf_path
from workbench.contracts import CaseSelection

ensure_cltf_path()
from cltf import prepare_non_detects


class ValidationError(ValueError):
    """Raised when uploaded data cannot support a CLTF model run."""


@dataclass(frozen=True)
class PreparedTable:
    data: pd.DataFrame
    warnings: list[str]


def _require_columns(
    data: pd.DataFrame,
    required: set[str],
    table_name: str,
) -> None:
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValidationError(
            f"{table_name} is missing required columns: {', '.join(missing)}"
        )


def _reject_legacy_columns(data: pd.DataFrame) -> None:
    legacy_columns = sorted(
        {"depth_mm", "relative_concentration", "concentration"}.intersection(
            data.columns
        )
    )
    if legacy_columns:
        raise ValidationError(
            "Uploaded observations use legacy columns "
            f"{', '.join(legacy_columns)}. Use depth_top_mm, "
            "depth_bottom_mm, and concentration_ug_kg."
        )


def _to_bool(values: pd.Series, default: bool = False) -> pd.Series:
    if values.empty:
        return values.astype(bool)
    if values.dtype == bool:
        return values.fillna(default).astype(bool)
    normalized = values.fillna(default).astype(str).str.strip().str.lower()
    return normalized.isin({"true", "t", "1", "yes", "y", "t0"})


def _numeric(
    data: pd.DataFrame,
    columns: list[str],
    table_name: str,
) -> pd.DataFrame:
    result = data.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
            if result[column].isna().any() and column != "detection_limit_ug_kg":
                raise ValidationError(
                    f"{table_name}.{column} contains non-numeric or missing values"
                )
    return result


def _infer_application_date(result: pd.DataFrame) -> pd.Timestamp:
    if "application_date" in result.columns:
        application_dates = pd.to_datetime(
            result["application_date"],
            errors="coerce",
        ).dropna()
        if application_dates.empty:
            raise ValidationError("observations.application_date contains no valid dates")
        return pd.Timestamp(application_dates.min()).normalize()

    if "is_t0" not in result.columns:
        if "timepoint" in result.columns:
            result["is_t0"] = (
                result["timepoint"].astype(str).str.strip().str.upper().eq("T0")
            )
        else:
            raise ValidationError(
                "observations requires application_date or is_t0/timepoint"
            )
    t0_dates = result.loc[result["is_t0"], "sample_date"]
    if t0_dates.empty:
        raise ValidationError(
            "At least one T0 row is required when application_date is absent"
        )
    return pd.Timestamp(t0_dates.min()).normalize()


def _validate_intervals(result: pd.DataFrame, site: dict[str, object]) -> None:
    bottom_depth = float(site["bottom_depth_mm"])
    invalid = (
        result["depth_top_mm"].lt(0)
        | result["depth_bottom_mm"].le(result["depth_top_mm"])
        | result["depth_bottom_mm"].gt(bottom_depth)
    )
    if invalid.any():
        raise ValidationError(
            "Observation depth intervals must be positive and fall within "
            f"the selected site's 0-{bottom_depth:g} mm profile."
        )


def prepare_uploaded_observations(
    raw: pd.DataFrame,
    site: dict[str, object],
    soil_group: str | None = None,
    herbicide: str | None = None,
) -> pd.DataFrame:
    """Prepare uploaded observation rows for CLTF fitting and simulation."""

    if raw.empty:
        raise ValidationError("observations is empty")
    _reject_legacy_columns(raw)
    _require_columns(
        raw,
        {
            "sample_date",
            "depth_top_mm",
            "depth_bottom_mm",
            "concentration_ug_kg",
        },
        "observations",
    )

    result = raw.copy()
    result["sample_date"] = pd.to_datetime(
        result["sample_date"],
        errors="coerce",
    ).dt.normalize()
    if result["sample_date"].isna().any():
        raise ValidationError("observations.sample_date contains invalid dates")

    result = _numeric(
        result,
        [
            "depth_top_mm",
            "depth_bottom_mm",
            "concentration_ug_kg",
            "detection_limit_ug_kg",
        ],
        "observations",
    )
    if "is_t0" in result.columns:
        result["is_t0"] = _to_bool(result["is_t0"])
    elif "timepoint" in result.columns:
        result["is_t0"] = (
            result["timepoint"].astype(str).str.strip().str.upper().eq("T0")
        )
    else:
        result["is_t0"] = False

    application_date = _infer_application_date(result)
    result["application_date"] = application_date
    result["days_since_application"] = (
        result["sample_date"] - application_date
    ).dt.days.astype(int)
    if result["days_since_application"].lt(0).any():
        raise ValidationError("observations contain dates before application_date")

    _validate_intervals(result, site)

    result["site_id"] = result.get("site_id", site["site_id"])
    result["soil_group"] = result.get(
        "soil_group",
        soil_group or site.get("default_soil_group", "Heavy"),
    )
    result["herbicide"] = result.get(
        "herbicide",
        herbicide or site.get("default_herbicide", "Imazapic"),
    )

    if "replicate_id" not in result.columns:
        result["replicate_id"] = (
            result.groupby(
                [
                    "site_id",
                    "soil_group",
                    "herbicide",
                    "depth_top_mm",
                    "depth_bottom_mm",
                    "days_since_application",
                ],
                dropna=False,
            ).cumcount()
            + 1
        )
    if "is_non_detect" not in result.columns:
        result["is_non_detect"] = False
    else:
        result["is_non_detect"] = _to_bool(result["is_non_detect"])
    if "detection_limit_ug_kg" not in result.columns:
        result["detection_limit_ug_kg"] = np.nan

    non_detects = prepare_non_detects(
        result["concentration_ug_kg"],
        result["is_non_detect"],
        result["detection_limit_ug_kg"],
    )
    result["analysis_concentration_ug_kg"] = non_detects[
        "analysis_concentration_ug_kg"
    ]
    result["lod_substituted"] = non_detects["lod_substituted"]
    result["excluded_zero"] = non_detects["excluded_zero"]
    result["is_zero_reported"] = (
        result["concentration_ug_kg"].eq(0) & ~result["lod_substituted"]
    )
    result["used_for_calibration"] = (
        ~result["is_t0"]
        & np.isfinite(result["analysis_concentration_ug_kg"])
        & result["analysis_concentration_ug_kg"].gt(0)
    )
    result["unit_status"] = result.get(
        "unit_status",
        "uploaded_ug_kg_dry_soil",
    )

    return result.reset_index(drop=True)


def list_cases(observations: pd.DataFrame) -> list[CaseSelection]:
    """Return unique site/soil/herbicide cases in prepared observations."""

    _require_columns(
        observations,
        {"site_id", "soil_group", "herbicide"},
        "observations",
    )
    cases = (
        observations[["site_id", "soil_group", "herbicide"]]
        .drop_duplicates()
        .sort_values(["site_id", "soil_group", "herbicide"])
    )
    return [
        CaseSelection(row.site_id, row.soil_group, row.herbicide)
        for row in cases.itertuples(index=False)
    ]
