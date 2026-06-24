#!/usr/bin/env python3
"""
Script: test_slga.py
Objective: Verify SLGA parsing, depth weighting, overrides, and normalized cache.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Local SLGA fixture and injected metadata/drill readers.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_slga.py -q
Dependencies: pathlib, numpy, pandas, pytest, cltf
"""

from pathlib import Path

import numpy as np
import pandas as pd

from cltf.slga import (
    fetch_slga_bulk_density,
    parse_slga_bulk_density,
    weight_bulk_density,
)


FIXTURE = Path("R/inst/extdata/slga_bulk_density_response.json")


def test_slga_parser_and_overlap_weighting() -> None:
    bands = parse_slga_bulk_density(FIXTURE)
    assert bands["depth_top_mm"].tolist() == [0.0, 50.0, 150.0]
    assert bands["depth_bottom_mm"].tolist() == [50.0, 150.0, 300.0]
    assert bands["estimate_g_cm3"].tolist() == [1.32, 1.38, 1.43]
    assert weight_bulk_density(bands, 0, 100).loc[
        0,
        "estimate_g_cm3",
    ] == 1.35
    assert weight_bulk_density(bands, 100, 300).loc[
        0,
        "estimate_g_cm3",
    ] == 1.4175


def test_manual_override_bypasses_network(tmp_path: Path) -> None:
    result = fetch_slga_bulk_density(
        -32.831016,
        135.14494,
        tmp_path,
        manual_override=[1.32, 1.38, 1.43],
        metadata_reader=lambda *_: (_ for _ in ()).throw(
            AssertionError("network metadata was requested")
        ),
        drill_reader=lambda *_: (_ for _ in ()).throw(
            AssertionError("network drill was requested")
        ),
    )
    assert result["estimate_g_cm3"].tolist() == [1.32, 1.38, 1.43]
    assert result["source"].tolist() == ["manual_override"] * 3


def test_slga_products_are_drilled_and_key_is_not_cached(
    tmp_path: Path,
) -> None:
    depths = ["000_005", "005_015", "015_030"]
    components = ["Modelled-Value", "Lower-CI", "Upper-CI"]
    rows = []
    suffixes = ["EV", "05", "95"]
    for component, suffix in zip(components, suffixes):
        for depth in depths:
            rows.append(
                {
                    "Component": component,
                    "COGsPath": (
                        f"https://example.test/BDW_{depth}_{suffix}.tif"
                    ),
                }
            )
    products = pd.DataFrame(rows)
    values = iter([1.32, 1.38, 1.43, 1.18, 1.22, 1.28, 1.46, 1.54, 1.58])

    result = fetch_slga_bulk_density(
        -32.831016,
        135.14494,
        tmp_path,
        api_key="test-key-not-for-cache",
        metadata_reader=lambda _: products,
        drill_reader=lambda url: {
            "value": next(values),
            "requested_url_has_key": "test-key-not-for-cache" in url,
        },
    )

    assert result["depth_bottom_mm"].tolist() == [50.0, 150.0, 300.0]
    np.testing.assert_allclose(
        result["estimate_g_cm3"],
        [1.32, 1.38, 1.43],
    )
    assert all(
        "credentialed SLGA v2 whole-earth" in source
        for source in result["source"]
    )
    cache_text = Path(result.attrs["cache_path"]).read_text()
    assert "test-key-not-for-cache" not in cache_text
