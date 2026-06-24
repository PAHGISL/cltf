#!/usr/bin/env python3
"""
Script: test_site_registry.py
Objective: Verify the CLTF app site registry and shared case lookup helpers.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared examples/data site registry and case directories.
Outputs: Pytest assertions.
Usage: python -m pytest apps/herbicide_workbench/tests/test_site_registry.py -q
Dependencies: workbench
"""

from __future__ import annotations

from workbench.contracts import CaseSelection
from workbench.site_registry import (
    available_herbicides,
    available_soils,
    case_input_dir,
    default_case,
    get_site,
    load_site_registry,
)


def test_default_showcase_is_nsw_griffith() -> None:
    registry = load_site_registry()

    assert default_case(registry) == CaseSelection(
        "NSW_Griffith",
        "Heavy",
        "Imazapic",
    )


def test_registry_exposes_site_geometry() -> None:
    site = get_site("SA_Minnipa")

    assert site["latitude"] == -32.831016
    assert site["top_depth_mm"] == 100
    assert site["bottom_depth_mm"] == 300


def test_registry_lists_available_inputs() -> None:
    soils = available_soils("NSW_Griffith")
    herbicides = available_herbicides("NSW_Griffith", "Heavy")
    input_dir = case_input_dir(CaseSelection("NSW_Griffith", "Heavy", "Imazapic"))

    assert soils == ["Heavy", "Light"]
    assert herbicides == ["Imazapic"]
    assert (input_dir / "case.json").exists()
    assert (input_dir / "observations.csv").exists()
