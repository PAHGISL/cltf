from __future__ import annotations

import json

import pandas as pd

from workbench.contracts import CaseSelection, ModelResult
from workbench.exports import build_export_artifacts


def test_build_export_artifacts_returns_named_files():
    predictions = pd.DataFrame({"days_since_application": [0], "top_rel_conc": [1.0]})
    forcing = pd.DataFrame({"date": pd.to_datetime(["2024-06-12"]), "rain_mm": [0.0]})
    observations = pd.DataFrame({"relative_concentration": [1.0]})
    site_config = pd.DataFrame({"site_id": ["SA"]})
    parameters = {"mu": 3.0}
    result = ModelResult(predictions=predictions, forcing=forcing, warnings=["example"], metadata={"adapter": "pyclt"})

    artifacts = build_export_artifacts(
        result=result,
        observations=observations,
        site_config=site_config,
        parameters=parameters,
        case=CaseSelection("SA", "Heavy", "Imazapic"),
        app_version="0.1.0",
    )

    assert set(artifacts) == {
        "model_output.csv",
        "observed_prepared.csv",
        "climate_prepared.csv",
        "site_config_prepared.csv",
        "parameters.csv",
        "run_metadata.json",
    }
    metadata = json.loads(artifacts["run_metadata.json"].decode("utf-8"))
    assert metadata["active_adapter"] == "pyclt"
    assert metadata["selected_case"]["site_id"] == "SA"
