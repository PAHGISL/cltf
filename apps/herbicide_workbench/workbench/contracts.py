"""Stable model contracts used by the workbench UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class CaseSelection:
    site_id: str
    soil_group: str
    herbicide: str


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    label: str
    default: float
    minimum: float
    maximum: float
    step: float
    description: str


@dataclass(frozen=True)
class InputBundle:
    climate: pd.DataFrame
    observations: pd.DataFrame
    site_config: pd.DataFrame
    case: CaseSelection


@dataclass
class ModelResult:
    predictions: pd.DataFrame
    forcing: pd.DataFrame
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class FitResult:
    parameters: dict[str, float]
    objective_value: float
    success: bool
    message: str
    result: ModelResult
    bound_hits: dict[str, bool]


class ModelAdapter(Protocol):
    name: str

    def parameter_specs(self) -> list[ParameterSpec]:
        """Return model-editable parameter definitions."""

    def default_parameters(self) -> dict[str, float]:
        """Return default parameter values keyed by parameter name."""

    def simulate(self, bundle: InputBundle, parameters: dict[str, float]) -> ModelResult:
        """Run a forward simulation for the selected case."""

    def fit(self, bundle: InputBundle, start_parameters: dict[str, float]) -> FitResult:
        """Fit model parameters for the selected case."""
