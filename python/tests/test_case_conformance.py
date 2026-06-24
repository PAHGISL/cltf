#!/usr/bin/env python3
"""
Script: test_case_conformance.py
Objective: Verify Python CLTF case outputs against committed R references.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared case inputs, Python runner, and committed R reference outputs.
Outputs: Pytest assertions for forward and ridge-aware calibration equivalence.
Usage: MPLBACKEND=Agg python -m pytest python/tests/test_case_conformance.py -q
Dependencies: json, os, pathlib, subprocess, sys, numpy, pandas, pytest, cltf
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from cltf import CLTFLayer, simulate_cltf, weight_bulk_density


ROOT = Path(__file__).parents[2]
REFERENCE = ROOT / "reference"
RUNNER = ROOT / "examples" / "python" / "run_reference_case.py"
CASES = (
    "nsw_griffith_heavy_imazapic",
    "sa_minnipa_heavy_imazapic",
)
MASS_COLUMNS = ["mass_top", "mass_bottom", "mass_below", "mass_degraded"]
CONCENTRATION_COLUMNS = [
    "concentration_top_ug_kg",
    "concentration_bottom_ug_kg",
]


@pytest.fixture(scope="session")
def tolerances() -> dict[str, float]:
    return json.loads((REFERENCE / "tolerances.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def python_outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("python-reference-cases")
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    outputs: dict[str, Path] = {}
    for case in CASES:
        output_dir = root / case
        subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--case",
                case,
                "--input-dir",
                str(ROOT / "examples" / "data" / case),
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            env=env,
        )
        outputs[case] = output_dir
    return outputs


def _reference_forward_predictions(case: str) -> pd.DataFrame:
    case_dir = REFERENCE / case
    forcing = pd.read_csv(case_dir / "climate_forcing.csv")
    bulk_density = pd.read_csv(case_dir / "bulk_density.csv")
    parameters = (
        pd.read_csv(case_dir / "fit_parameters.csv")
        .set_index("parameter")["estimate"]
        .to_dict()
    )
    metadata = json.loads((case_dir / "metadata.json").read_text(encoding="utf-8"))
    top_thickness = float(metadata["model"]["top_thickness_mm"])
    bottom_thickness = float(metadata["model"]["bottom_thickness_mm"])
    top_density = weight_bulk_density(
        bulk_density,
        0.0,
        top_thickness,
    ).loc[0, "estimate_g_cm3"]
    bottom_density = weight_bulk_density(
        bulk_density,
        top_thickness,
        top_thickness + bottom_thickness,
    ).loc[0, "estimate_g_cm3"]
    return simulate_cltf(
        forcing["time_days"],
        forcing["cumulative_infiltration_mm"],
        CLTFLayer(
            parameters["mu"],
            parameters["sigma"],
            parameters["R_top"],
            top_thickness,
        ),
        CLTFLayer(
            parameters["mu"],
            parameters["sigma"],
            parameters["R_bottom"],
            bottom_thickness,
        ),
        parameters["k"],
        metadata["application_rate"]["value_g_ha"],
        top_density,
        bottom_density,
        effective_porosity=metadata["model"]["effective_porosity"],
        method=metadata["model"]["convolution_method"],
        n_steps=metadata["model"]["convolution_steps"],
    )


def _selected_objective(path: Path) -> float:
    diagnostics = pd.read_csv(path / "fit_diagnostics.csv")
    return float(diagnostics.loc[diagnostics["selected"], "objective"].iloc[0])


def _transport_scales(path: Path) -> np.ndarray:
    parameters = (
        pd.read_csv(path / "fit_parameters.csv")
        .set_index("parameter")["estimate"]
        .to_dict()
    )
    return np.asarray(
        [
            parameters["mu"] * parameters["R_top"],
            parameters["mu"] * parameters["R_bottom"],
        ],
        dtype=float,
    )


def test_python_forward_model_reproduces_r_reference_predictions(
    tolerances: dict[str, float],
) -> None:
    for case in CASES:
        expected = pd.read_csv(REFERENCE / case / "predictions.csv")
        actual = _reference_forward_predictions(case)
        np.testing.assert_allclose(
            actual[MASS_COLUMNS],
            expected[MASS_COLUMNS],
            atol=tolerances["absolute"],
            rtol=tolerances["relative"],
        )
        np.testing.assert_allclose(
            actual[CONCENTRATION_COLUMNS],
            expected[CONCENTRATION_COLUMNS],
            atol=tolerances["absolute"],
            rtol=tolerances["relative"],
        )


def test_python_runner_matches_r_cases_with_ridge_aware_tolerances(
    python_outputs: dict[str, Path],
    tolerances: dict[str, float],
) -> None:
    for case, python_dir in python_outputs.items():
        reference_dir = REFERENCE / case
        python_predictions = pd.read_csv(python_dir / "predictions.csv")
        r_predictions = pd.read_csv(reference_dir / "predictions.csv")
        np.testing.assert_allclose(
            python_predictions[MASS_COLUMNS],
            r_predictions[MASS_COLUMNS],
            atol=tolerances["case_runner_mass_absolute"],
            rtol=tolerances["case_runner_relative"],
        )
        np.testing.assert_allclose(
            python_predictions[CONCENTRATION_COLUMNS],
            r_predictions[CONCENTRATION_COLUMNS],
            atol=tolerances["case_runner_concentration_absolute"],
            rtol=tolerances["case_runner_relative"],
        )
        assert abs(
            _selected_objective(python_dir) - _selected_objective(reference_dir)
        ) <= tolerances["case_calibration_objective_absolute"]
        np.testing.assert_allclose(
            _transport_scales(python_dir),
            _transport_scales(reference_dir),
            atol=tolerances["case_transport_scale_absolute"],
            rtol=tolerances["case_transport_scale_relative"],
        )
