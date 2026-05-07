"""Export helpers for workbench run artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from workbench.contracts import CaseSelection, ModelResult


def _csv_bytes(data: pd.DataFrame) -> bytes:
    return data.to_csv(index=False).encode("utf-8")


def build_export_artifacts(
    result: ModelResult,
    observations: pd.DataFrame,
    site_config: pd.DataFrame,
    parameters: dict[str, float],
    case: CaseSelection,
    app_version: str,
) -> dict[str, bytes]:
    parameter_table = pd.DataFrame([{"parameter": key, "value": value} for key, value in parameters.items()])
    metadata = {
        "app_version": app_version,
        "active_adapter": result.metadata.get("adapter", "unknown"),
        "selected_case": {
            "site_id": case.site_id,
            "soil_group": case.soil_group,
            "herbicide": case.herbicide,
        },
        "parameter_values": parameters,
        "warnings": result.warnings,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "model_output.csv": _csv_bytes(result.predictions),
        "observed_prepared.csv": _csv_bytes(observations),
        "climate_prepared.csv": _csv_bytes(result.forcing),
        "site_config_prepared.csv": _csv_bytes(site_config),
        "parameters.csv": _csv_bytes(parameter_table),
        "run_metadata.json": json.dumps(metadata, indent=2).encode("utf-8"),
    }
