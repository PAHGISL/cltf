#!/usr/bin/env python3
"""
Script: test_silo.py
Objective: Verify SILO coordinate rounding, parsing, and cache-first retrieval.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Local SILO CSV fixture and injected download functions.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_silo.py -q
Dependencies: pathlib, shutil, pandas, pytest, cltf
"""

from pathlib import Path
import shutil

import pandas as pd
import pytest

from cltf.silo import fetch_silo_point, parse_silo_csv, round_silo_coordinate


FIXTURE = Path("R/inst/extdata/sa_silo.csv")


def test_silo_coordinate_rounding_and_parser() -> None:
    assert round_silo_coordinate(-32.831016) == pytest.approx(-32.85)
    assert round_silo_coordinate(135.14494) == pytest.approx(135.15)
    result = parse_silo_csv(FIXTURE)
    assert result.columns.tolist() == ["date", "jdays", "rain_mm", "Tmax", "Tmin"]
    assert result["date"].tolist() == [
        pd.Timestamp("2024-06-12"),
        pd.Timestamp("2024-06-13"),
    ]
    assert result["rain_mm"].tolist() == [0.0, 3.4]


def test_silo_cache_prevents_second_request(tmp_path: Path) -> None:
    calls = 0

    def downloader(url: str, destination: Path) -> None:
        nonlocal calls
        calls += 1
        assert "test%40example.org" in url
        shutil.copy(FIXTURE, destination)

    first = fetch_silo_point(
        -32.831016,
        135.14494,
        "2024-06-12",
        "2024-06-13",
        tmp_path,
        username="test@example.org",
        password="testpassword",
        downloader=downloader,
    )
    second = fetch_silo_point(
        -32.831016,
        135.14494,
        "2024-06-12",
        "2024-06-13",
        tmp_path,
        downloader=lambda *_: pytest.fail("cache was not used"),
    )
    assert calls == 1
    pd.testing.assert_frame_equal(first, second)
    metadata = Path(second.attrs["metadata_path"]).read_text()
    assert "testpassword" not in metadata
    assert "test@example.org" not in metadata
