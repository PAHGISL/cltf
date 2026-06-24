#!/usr/bin/env python3
"""
Script: test_data_services.py
Objective: Verify cache-first climate and soil preparation for the CLTF app.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared example SILO and SLGA cache files.
Outputs: Pytest assertions for external CLTF inputs.
Usage: python -m pytest apps/herbicide_workbench/tests/test_data_services.py -q
Dependencies: pytest, workbench
"""

from __future__ import annotations

from workbench.contracts import CaseSelection
from workbench.data_services import prepare_external_inputs


def test_showcase_uses_committed_cache_without_credentials() -> None:
    result = prepare_external_inputs(
        CaseSelection("NSW_Griffith", "Heavy", "Imazapic"),
        environment={},
    )

    assert len(result.forcing) == 147
    assert len(result.bulk_density) == 3
    assert result.metadata["climate_source"] == "committed_cache"
    assert result.metadata["soil_source"] == "committed_cache"
    assert result.forcing["daily_infiltration_mm"].ge(0).all()
    assert result.forcing["cumulative_infiltration_mm"].is_monotonic_increasing
    assert result.top_bulk_density_g_cm3 > 0
    assert result.bottom_bulk_density_g_cm3 > 0


def test_api_failure_falls_back_to_cache(monkeypatch) -> None:
    def fail_silo(*args: object, **kwargs: object) -> object:
        raise RuntimeError("offline")

    monkeypatch.setattr("cltf.silo.fetch_silo_point", fail_silo)

    result = prepare_external_inputs(
        CaseSelection("SA_Minnipa", "Heavy", "Imazapic"),
        environment={"SILO_USERNAME": "x", "SILO_PASSWORD": "y"},
        refresh_climate=True,
    )

    assert result.metadata["climate_source"] == "committed_cache"
    assert any("fallback" in warning.lower() for warning in result.warnings)
