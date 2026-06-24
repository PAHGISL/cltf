#!/usr/bin/env python3
"""
Script: assessment.py
Objective: Select and summarize CLTF residue assessment dates for the workbench.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Application dates, observed forcing dates, and CLTF prediction tables.
Outputs: Assessment dates and AssessmentResult summaries.
Usage: Import date and summary helpers from workbench.assessment.
Dependencies: pandas, workbench
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from workbench.contracts import AssessmentResult


def _normalize_date(value: object) -> pd.Timestamp:
    date = pd.Timestamp(value).normalize()
    if pd.isna(date):
        raise ValueError("Assessment date is invalid")
    return date


def _available_final_date(available_dates: Iterable[object]) -> pd.Timestamp:
    dates = pd.to_datetime(list(available_dates), errors="coerce")
    if len(dates) == 0 or pd.isna(dates).all():
        raise ValueError("At least one observed climate date is required")
    return pd.Timestamp(dates.max()).normalize()


def validate_assessment_date(
    date: object,
    application_date: object,
    final_date: object,
) -> pd.Timestamp:
    """Validate that an assessment date is inside the observed forcing period."""

    assessment = _normalize_date(date)
    application = _normalize_date(application_date)
    final = _normalize_date(final_date)
    if assessment < application:
        raise ValueError("Assessment date cannot be before application date")
    if assessment > final:
        raise ValueError(
            "Assessment date cannot exceed the period covered by observed climate"
        )
    return assessment


def assessment_date_from_preset(
    application_date: object,
    days: int,
    final_date: object,
) -> pd.Timestamp:
    """Return a preset day-after-application assessment date after validation."""

    if days < 0:
        raise ValueError("Assessment preset days must be non-negative")
    application = _normalize_date(application_date)
    assessment = application + pd.Timedelta(days=int(days))
    return validate_assessment_date(assessment, application, final_date)


def default_assessment_date(
    application_date: object,
    available_dates: Iterable[object],
) -> pd.Timestamp:
    """Default to 90 days after application, capped by observed forcing."""

    application = _normalize_date(application_date)
    final = _available_final_date(available_dates)
    preferred = application + pd.Timedelta(days=90)
    return validate_assessment_date(min(preferred, final), application, final)


def summarize_assessment(
    predictions: pd.DataFrame,
    date: object,
) -> AssessmentResult:
    """Extract the CLTF prediction row for one residue assessment date."""

    required = {
        "date",
        "time_days",
        "concentration_top_ug_kg",
        "concentration_bottom_ug_kg",
        "mass_top",
        "mass_bottom",
    }
    missing = sorted(required.difference(predictions.columns))
    if missing:
        raise ValueError(
            "Prediction table is missing required columns: "
            f"{', '.join(missing)}"
        )

    assessment = _normalize_date(date)
    prediction_dates = pd.to_datetime(
        predictions["date"],
        errors="coerce",
    ).dt.normalize()
    matches = predictions.loc[prediction_dates.eq(assessment)]
    if matches.empty:
        raise ValueError(
            f"Prediction table contains no exact row for {assessment.date()}"
        )
    row = matches.iloc[0]
    return AssessmentResult(
        date=assessment,
        time_days=int(row["time_days"]),
        concentration_top_ug_kg=float(row["concentration_top_ug_kg"]),
        concentration_bottom_ug_kg=float(row["concentration_bottom_ug_kg"]),
        resident_profile_fraction=float(row["mass_top"] + row["mass_bottom"]),
    )
