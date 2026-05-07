from __future__ import annotations

import numpy as np
import pandas as pd

from workbench.adapters import PyCLTAdapter
from workbench.contracts import CaseSelection, InputBundle


def make_bundle() -> InputBundle:
    climate = pd.DataFrame(
        {
            "date": pd.date_range("2024-06-12", periods=20, freq="D"),
            "days_since_application": np.arange(20),
            "rain_mm": [0.0] * 20,
            "Tmax": [18.0] * 20,
            "Tmin": [8.0] * 20,
            "jdays": np.arange(164, 184),
            "et0_mm": [1.0] * 20,
            "cumulative_infiltration_mm": np.linspace(0.0, 30.0, 20),
        }
    )
    observations = pd.DataFrame(
        {
            "site_id": ["SA", "SA", "SA", "SA"],
            "soil_group": ["Heavy", "Heavy", "Heavy", "Heavy"],
            "herbicide": ["Imazapic", "Imazapic", "Imazapic", "Imazapic"],
            "depth_mm": [100, 300, 100, 300],
            "days_since_application": [0, 0, 10, 10],
            "relative_concentration": [1.0, 0.0001, 0.8, 0.02],
            "replicate_id": [1, 1, 1, 1],
        }
    )
    site_config = pd.DataFrame(
        {
            "site_id": ["SA"],
            "soil_group": ["Heavy"],
            "application_date": pd.to_datetime(["2024-06-12"]),
            "top_thickness_mm": [100],
            "reference_depth_mm": [100],
            "bottom_depth_mm": [300],
            "representative_lat": [-32.85],
            "representative_lon": [135.15],
        }
    )
    return InputBundle(
        climate=climate,
        observations=observations,
        site_config=site_config,
        case=CaseSelection("SA", "Heavy", "Imazapic"),
    )


def test_parameter_specs_match_default_parameters():
    adapter = PyCLTAdapter()

    spec_names = {spec.name for spec in adapter.parameter_specs()}
    defaults = adapter.default_parameters()

    assert spec_names == set(defaults)
    assert defaults["mu"] == 3.0
    assert "et_factor" in defaults


def test_simulate_returns_expected_schema():
    adapter = PyCLTAdapter()
    bundle = make_bundle()

    result = adapter.simulate(bundle, adapter.default_parameters())

    assert result.metadata["adapter"] == "pyclt"
    assert list(result.predictions.columns) == [
        "site_id",
        "soil_group",
        "herbicide",
        "date",
        "days_since_application",
        "top_rel_conc",
        "subsoil_rel_conc",
        "run_type",
    ]
    assert len(result.predictions) == len(bundle.climate)
    assert result.predictions["top_rel_conc"].notna().all()


def test_fit_returns_parameters_and_bound_hits():
    adapter = PyCLTAdapter(maxiter=3, maxfun=8)
    bundle = make_bundle()

    fit = adapter.fit(bundle, adapter.default_parameters())

    assert set(fit.parameters) == set(adapter.default_parameters())
    assert np.isfinite(fit.objective_value)
    assert set(fit.bound_hits) == set(adapter.default_parameters())
    assert fit.result.predictions["run_type"].eq("fitted").all()
