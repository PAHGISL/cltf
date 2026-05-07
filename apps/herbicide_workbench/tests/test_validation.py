from __future__ import annotations

import pandas as pd
import pytest

from workbench.contracts import CaseSelection
from workbench.validation import (
    ValidationError,
    build_input_bundle,
    list_cases,
    prepare_climate,
    prepare_observations,
    prepare_site_config,
)


def test_prepare_climate_derives_jdays_et_and_infiltration():
    raw = pd.DataFrame(
        {
            "date": ["2024-06-12", "2024-06-13"],
            "rain_mm": [0.0, 10.0],
            "Tmax": [18.0, 19.0],
            "Tmin": [8.0, 9.0],
        }
    )

    climate, warnings = prepare_climate(raw, latitude=-32.85, et_factor=1.0)

    assert warnings == []
    assert list(climate["jdays"]) == [164, 165]
    assert "et0_mm" in climate.columns
    assert "cumulative_infiltration_mm" in climate.columns
    assert climate["cumulative_infiltration_mm"].iloc[-1] >= 0


def test_prepare_climate_requires_latitude_when_et_missing():
    raw = pd.DataFrame(
        {
            "date": ["2024-06-12"],
            "rain_mm": [0.0],
            "Tmax": [18.0],
            "Tmin": [8.0],
        }
    )

    with pytest.raises(ValidationError, match="representative_lat"):
        prepare_climate(raw, latitude=None, et_factor=1.0)


def test_prepare_climate_preserves_uploaded_days_since_application():
    raw = pd.DataFrame(
        {
            "date": ["2024-06-12", "2024-06-13"],
            "days_since_application": [10, 11],
            "rain_mm": [0.0, 10.0],
            "Tmax": [18.0, 19.0],
            "Tmin": [8.0, 9.0],
            "et0_mm": [1.0, 1.0],
            "cumulative_infiltration_mm": [0.0, 9.0],
        }
    )

    climate, _ = prepare_climate(raw, latitude=None, et_factor=1.0)

    assert list(climate["days_since_application"]) == [10, 11]


def test_prepare_observations_calculates_relative_concentration():
    raw = pd.DataFrame(
        {
            "site_id": ["SA", "SA"],
            "soil_group": ["Heavy", "Heavy"],
            "herbicide": ["Imazapic", "Imazapic"],
            "depth_mm": [100, 100],
            "sample_date": ["2024-06-12", "2024-06-27"],
            "concentration": [20.0, 5.0],
            "is_t0": [True, False],
        }
    )
    site_config = pd.DataFrame(
        {
            "site_id": ["SA"],
            "soil_group": ["Heavy"],
            "application_date": ["2024-06-12"],
            "top_thickness_mm": [100],
            "reference_depth_mm": [100],
            "bottom_depth_mm": [300],
            "representative_lat": [-32.85],
            "representative_lon": [135.15],
        }
    )

    observations, warnings = prepare_observations(raw, site_config)

    assert warnings == ["relative_concentration calculated from top-layer T0 concentration"]
    assert list(observations["days_since_application"]) == [0, 15]
    assert list(observations["relative_concentration"]) == [1.0, 0.25]


def test_list_cases_returns_unique_sorted_cases():
    observations = pd.DataFrame(
        {
            "site_id": ["B", "A", "A"],
            "soil_group": ["Light", "Heavy", "Heavy"],
            "herbicide": ["H2", "H1", "H1"],
        }
    )

    assert list_cases(observations) == [CaseSelection("A", "Heavy", "H1"), CaseSelection("B", "Light", "H2")]


def test_build_input_bundle_filters_selected_case():
    climate = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-06-12", "2024-06-13"]),
            "days_since_application": [0, 1],
            "rain_mm": [0.0, 0.0],
            "Tmax": [18.0, 19.0],
            "Tmin": [8.0, 9.0],
            "jdays": [164, 165],
            "et0_mm": [1.0, 1.0],
            "cumulative_infiltration_mm": [0.0, 0.0],
        }
    )
    observations = pd.DataFrame(
        {
            "site_id": ["SA", "SA", "NSW"],
            "soil_group": ["Heavy", "Light", "Heavy"],
            "herbicide": ["Imazapic", "Imazapic", "Imazapic"],
            "depth_mm": [100, 100, 150],
            "days_since_application": [0, 0, 0],
            "relative_concentration": [1.0, 1.0, 1.0],
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

    bundle = build_input_bundle(
        climate=climate,
        observations=observations,
        site_config=site_config,
        case=CaseSelection("SA", "Heavy", "Imazapic"),
    )

    assert len(bundle.observations) == 1
    assert bundle.case.site_id == "SA"


def test_build_input_bundle_filters_climate_when_site_id_is_present():
    climate = pd.DataFrame(
        {
            "site_id": ["NSW", "SA", "SA"],
            "date": pd.to_datetime(["2024-06-12", "2024-06-12", "2024-06-13"]),
            "days_since_application": [0, 0, 1],
            "rain_mm": [0.0, 0.0, 1.0],
            "Tmax": [17.0, 18.0, 19.0],
            "Tmin": [7.0, 8.0, 9.0],
            "jdays": [164, 164, 165],
            "et0_mm": [1.0, 1.0, 1.0],
            "cumulative_infiltration_mm": [0.0, 0.0, 0.0],
        }
    )
    observations = pd.DataFrame(
        {
            "site_id": ["SA"],
            "soil_group": ["Heavy"],
            "herbicide": ["Imazapic"],
            "depth_mm": [100],
            "days_since_application": [0],
            "relative_concentration": [1.0],
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

    bundle = build_input_bundle(
        climate=climate,
        observations=observations,
        site_config=site_config,
        case=CaseSelection("SA", "Heavy", "Imazapic"),
    )

    assert list(bundle.climate["site_id"]) == ["SA", "SA"]
