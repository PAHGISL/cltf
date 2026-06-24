#!/usr/bin/env python3
"""
Script: contracts.py
Objective: Define stable CLTF workbench data contracts.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Prepared site, observation, forcing, soil, fit, and assessment values.
Outputs: Dataclasses shared by the Streamlit app and tests.
Usage: Import contract dataclasses from workbench.contracts.
Dependencies: dataclasses, pandas, cltf
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from cltf import CLTFFit


@dataclass(frozen=True)
class CaseSelection:
    site_id: str
    soil_group: str
    herbicide: str


@dataclass(frozen=True)
class ExternalInputs:
    forcing: pd.DataFrame
    bulk_density: pd.DataFrame
    top_bulk_density_g_cm3: float
    bottom_bulk_density_g_cm3: float
    warnings: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True)
class PreparedInputs:
    case: CaseSelection
    site: dict[str, object]
    observations: pd.DataFrame
    forcing: pd.DataFrame
    bulk_density: pd.DataFrame
    application_date: pd.Timestamp
    application_rate_g_ha: float
    top_bulk_density_g_cm3: float
    bottom_bulk_density_g_cm3: float


@dataclass(frozen=True)
class AssessmentResult:
    date: pd.Timestamp
    time_days: int
    concentration_top_ug_kg: float
    concentration_bottom_ug_kg: float
    resident_profile_fraction: float


@dataclass
class RunResult:
    parameters: dict[str, float]
    predictions: pd.DataFrame
    fit: CLTFFit | None
    assessment: AssessmentResult
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
