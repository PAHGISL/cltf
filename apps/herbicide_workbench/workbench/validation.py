"""Validation and preprocessing for uploaded workbench tables."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from workbench.config import ensure_pyclt_path
from workbench.contracts import CaseSelection, InputBundle


class ValidationError(ValueError):
    """Raised when uploaded data cannot support a model run."""


@dataclass(frozen=True)
class PreparedTable:
    data: pd.DataFrame
    warnings: list[str]


def _require_columns(data: pd.DataFrame, required: set[str], table_name: str) -> None:
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValidationError(f"{table_name} is missing required columns: {', '.join(missing)}")


def _numeric(data: pd.DataFrame, columns: list[str], table_name: str) -> pd.DataFrame:
    result = data.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
            if result[column].isna().any():
                raise ValidationError(f"{table_name}.{column} contains non-numeric or missing values")
    return result


def prepare_site_config(raw: pd.DataFrame | None) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()

    result = raw.copy()
    _require_columns(result, {"site_id", "soil_group"}, "site_config")
    for column in ("application_date", "final_sample_date"):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce")
            if result[column].isna().any():
                raise ValidationError(f"site_config.{column} contains invalid dates")
    result = _numeric(
        result,
        [
            "representative_lat",
            "representative_lon",
            "top_thickness_mm",
            "reference_depth_mm",
            "bottom_depth_mm",
        ],
        "site_config",
    )
    return result


def prepare_climate(raw: pd.DataFrame, latitude: float | None, et_factor: float = 1.0) -> tuple[pd.DataFrame, list[str]]:
    _require_columns(raw, {"date", "rain_mm", "Tmax", "Tmin"}, "climate")
    result = raw.copy()
    warnings: list[str] = []
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    if result["date"].isna().any():
        raise ValidationError("climate.date contains invalid dates")
    result = _numeric(
        result,
        ["rain_mm", "Tmax", "Tmin", "et0_mm", "cumulative_infiltration_mm", "irrigation_mm", "days_since_application"],
        "climate",
    )
    result = result.sort_values("date").reset_index(drop=True)
    if "jdays" not in result.columns:
        result["jdays"] = result["date"].dt.dayofyear
    if "et0_mm" not in result.columns:
        if latitude is None or pd.isna(latitude):
            raise ValidationError("representative_lat is required when climate.et0_mm is not uploaded")
        ensure_pyclt_path()
        from pyclt.climate import calc_et

        result["et0_mm"] = calc_et(latitude_deg=float(latitude), data=result[["jdays", "Tmax", "Tmin"]])
    if "irrigation_mm" not in result.columns:
        result["irrigation_mm"] = 0.0
    if "cumulative_infiltration_mm" not in result.columns:
        ensure_pyclt_path()
        from pyclt.infiltration import cumulative_infiltration

        water_in = result["rain_mm"].to_numpy(dtype=float) + result["irrigation_mm"].to_numpy(dtype=float)
        result["cumulative_infiltration_mm"] = cumulative_infiltration(
            water_in,
            result["et0_mm"].to_numpy(dtype=float),
            et_factor=float(et_factor),
        )
    if "days_since_application" not in result.columns:
        result["days_since_application"] = np.arange(len(result), dtype=int)
    result["days_since_application"] = result["days_since_application"].astype(int)
    return result, warnings


def prepare_observations(raw: pd.DataFrame, site_config: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    required = {"site_id", "soil_group", "herbicide", "depth_mm"}
    _require_columns(raw, required, "observations")
    if "sample_date" not in raw.columns and "days_since_application" not in raw.columns:
        raise ValidationError("observations requires either sample_date or days_since_application")
    if "relative_concentration" not in raw.columns and "concentration" not in raw.columns:
        raise ValidationError("observations requires either relative_concentration or concentration")

    result = raw.copy()
    warnings: list[str] = []
    result = _numeric(result, ["depth_mm", "days_since_application", "relative_concentration", "concentration"], "observations")
    if "sample_date" in result.columns:
        result["sample_date"] = pd.to_datetime(result["sample_date"], errors="coerce").dt.normalize()
        if result["sample_date"].isna().any():
            raise ValidationError("observations.sample_date contains invalid dates")

    if "days_since_application" not in result.columns:
        if site_config.empty or "application_date" not in site_config.columns:
            raise ValidationError("site_config.application_date is required when observations.days_since_application is missing")
        app_dates = site_config[["site_id", "soil_group", "application_date"]].drop_duplicates().copy()
        app_dates["application_date"] = pd.to_datetime(app_dates["application_date"], errors="coerce")
        if app_dates["application_date"].isna().any():
            raise ValidationError("site_config.application_date contains invalid dates")
        result = result.merge(app_dates, on=["site_id", "soil_group"], how="left")
        if result["application_date"].isna().any():
            raise ValidationError("application_date is missing for one or more observation rows")
        result["days_since_application"] = (result["sample_date"] - result["application_date"]).dt.days

    if "relative_concentration" not in result.columns:
        if "is_t0" not in result.columns:
            raise ValidationError("observations.is_t0 is required to infer relative_concentration from concentration")
        if site_config.empty or "top_thickness_mm" not in site_config.columns:
            raise ValidationError("site_config.top_thickness_mm is required to infer relative_concentration")
        depth_lookup = site_config[["site_id", "soil_group", "top_thickness_mm"]].drop_duplicates()
        result = result.merge(depth_lookup, on=["site_id", "soil_group"], how="left")
        top_t0 = (
            result.loc[result["is_t0"].astype(bool) & (result["depth_mm"] == result["top_thickness_mm"])]
            .groupby(["site_id", "soil_group", "herbicide"], as_index=False)["concentration"]
            .mean()
            .rename(columns={"concentration": "t0_top_mean"})
        )
        result = result.merge(top_t0, on=["site_id", "soil_group", "herbicide"], how="left")
        if result["t0_top_mean"].isna().any():
            raise ValidationError("top-layer T0 concentration is missing for relative concentration calculation")
        result["relative_concentration"] = result["concentration"] / result["t0_top_mean"]
        warnings.append("relative_concentration calculated from top-layer T0 concentration")

    if "replicate_id" not in result.columns:
        result["replicate_id"] = (
            result.groupby(["site_id", "soil_group", "herbicide", "depth_mm", "days_since_application"]).cumcount() + 1
        )
    return result.reset_index(drop=True), warnings


def list_cases(observations: pd.DataFrame) -> list[CaseSelection]:
    cases = (
        observations[["site_id", "soil_group", "herbicide"]]
        .drop_duplicates()
        .sort_values(["site_id", "soil_group", "herbicide"])
    )
    return [CaseSelection(row.site_id, row.soil_group, row.herbicide) for row in cases.itertuples(index=False)]


def build_input_bundle(
    climate: pd.DataFrame,
    observations: pd.DataFrame,
    site_config: pd.DataFrame,
    case: CaseSelection,
) -> InputBundle:
    case_obs = observations.loc[
        (observations["site_id"] == case.site_id)
        & (observations["soil_group"] == case.soil_group)
        & (observations["herbicide"] == case.herbicide)
    ].copy()
    if case_obs.empty:
        raise ValidationError(f"No observations found for {case.site_id} / {case.soil_group} / {case.herbicide}")

    case_site = site_config.loc[
        (site_config["site_id"] == case.site_id) & (site_config["soil_group"] == case.soil_group)
    ].copy()
    if case_site.empty:
        raise ValidationError(f"No site configuration found for {case.site_id} / {case.soil_group}")

    case_climate = climate.copy()
    if "site_id" in case_climate.columns:
        case_climate = case_climate.loc[case_climate["site_id"] == case.site_id].copy()
        if case_climate.empty:
            raise ValidationError(f"No climate rows found for {case.site_id}")

    return InputBundle(climate=case_climate, observations=case_obs, site_config=case_site, case=case)
