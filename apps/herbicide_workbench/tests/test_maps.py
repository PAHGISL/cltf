#!/usr/bin/env python3
"""
Script: test_maps.py
Objective: Verify CLTF workbench pydeck site-map style and layers.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared CLTF site registry records and optional Mapbox token.
Outputs: Pytest assertions for map deck configuration.
Usage: python -m pytest apps/herbicide_workbench/tests/test_maps.py -q
Dependencies: pydeck, workbench
"""

from __future__ import annotations

from workbench.maps import build_site_map
from workbench.site_registry import get_site


def test_map_uses_satellite_style_when_token_exists() -> None:
    deck = build_site_map(get_site("NSW_Griffith"), mapbox_token="token")

    assert deck.map_style == "mapbox://styles/mapbox/satellite-streets-v12"


def test_map_uses_attributed_fallback_without_token() -> None:
    deck = build_site_map(get_site("SA_Minnipa"), mapbox_token="")

    assert deck.map_style != "mapbox://styles/mapbox/satellite-streets-v12"
    assert len(deck.layers) >= 2
