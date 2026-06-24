#!/usr/bin/env python3
"""
Script: test_reference_runner.py
Objective: Verify the shared Python reference runner command-line workflow.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared case inputs under examples/data.
Outputs: Pytest assertions for runner artifacts.
Usage: python -m pytest python/tests/test_reference_runner.py -q
Dependencies: os, pathlib, subprocess, sys
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[2]


def test_python_runner_writes_expected_schema(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / "python" / "run_reference_case.py"),
            "--case",
            "nsw_griffith_heavy_imazapic",
            "--input-dir",
            str(ROOT / "examples" / "data" / "nsw_griffith_heavy_imazapic"),
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        env=env,
    )
    expected = {
        "bulk_density.csv",
        "climate_forcing.csv",
        "fit_diagnostics.csv",
        "fit_parameters.csv",
        "metadata.json",
        "objective_profiles.csv",
        "observations_prepared.csv",
        "predictions.csv",
    }
    assert expected <= {path.name for path in tmp_path.iterdir()}
