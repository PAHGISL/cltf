#!/usr/bin/env python3
"""
Script: test_shared_cases.py
Objective: Verify shared NSW and SA site/case inputs and normalized datasets.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared JSON, observation CSV, SILO CSV, and bulk-density inputs.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_shared_cases.py -q
Dependencies: json, pathlib, pandas, cltf
"""

import json
from pathlib import Path

import pandas as pd

from cltf import parse_silo_csv


ROOT = Path(__file__).parents[2]
DATA = ROOT / "examples" / "data"


def test_site_registry_defines_approved_sites() -> None:
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))
    assert [site["site_id"] for site in sites] == [
        "NSW_Griffith",
        "SA_Minnipa",
    ]
    assert [site["top_depth_mm"] for site in sites] == [150, 100]
    assert [site["bottom_depth_mm"] for site in sites] == [300, 300]


def test_case_configuration_matches_site_registry() -> None:
    for case_name, application_date, final_date in (
        ("nsw_griffith_heavy_imazapic", "2024-04-26", "2024-09-19"),
        ("sa_minnipa_heavy_imazapic", "2024-06-12", "2024-10-28"),
    ):
        case = json.loads(
            (DATA / case_name / "case.json").read_text(encoding="utf-8")
        )
        assert case["soil_group"] == "Heavy"
        assert case["herbicide"] == "Imazapic"
        assert case["application_date"] == application_date
        assert case["final_date"] == final_date


def test_shared_observations_preserve_replicates() -> None:
    nsw = pd.read_csv(
        DATA / "nsw_griffith_heavy_imazapic" / "observations.csv"
    )
    sa = pd.read_csv(
        DATA / "sa_minnipa_heavy_imazapic" / "observations.csv"
    )
    assert len(nsw) == 30
    assert int(nsw["used_for_calibration"].sum()) == 24
    assert sorted(nsw["depth_bottom_mm"].unique()) == [150.0, 300.0]
    assert len(sa) == 31
    assert int(sa["used_for_calibration"].sum()) == 25


def test_shared_silo_forcing_covers_observation_periods() -> None:
    nsw = parse_silo_csv(
        DATA / "nsw_griffith_heavy_imazapic" / "silo.csv"
    )
    sa = parse_silo_csv(
        DATA / "sa_minnipa_heavy_imazapic" / "silo.csv"
    )
    assert len(nsw) == 147
    assert nsw["date"].min() == pd.Timestamp("2024-04-26")
    assert nsw["date"].max() == pd.Timestamp("2024-09-19")
    assert len(sa) == 139
    assert sa["date"].min() == pd.Timestamp("2024-06-12")
    assert sa["date"].max() == pd.Timestamp("2024-10-28")
