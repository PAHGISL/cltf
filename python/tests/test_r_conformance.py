#!/usr/bin/env python3
"""
Script: test_r_conformance.py
Objective: Verify Python primitives against shared expected R outputs.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Language-neutral primitive and tolerance JSON fixtures.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_r_conformance.py -q
Dependencies: json, pathlib, numpy, cltf
"""

import json
from pathlib import Path

import numpy as np

from cltf import (
    CLTFLayer,
    apply_elapsed_degradation,
    cltf_cdf,
    cltf_layer_probabilities,
    cltf_pdf,
    cumulative_infiltration,
    daily_infiltration,
    first_passage_time,
    pet_from_temperature,
    resident_concentration_ug_kg,
)


REFERENCE = Path(__file__).parents[2] / "reference"


def _load(name: str) -> dict:
    return json.loads((REFERENCE / name).read_text(encoding="utf-8"))


def _layer(values: dict) -> CLTFLayer:
    return CLTFLayer(
        values["mu"],
        values["sigma"],
        values["retardation"],
        values["thickness_mm"],
    )


def test_python_primitives_match_shared_r_outputs() -> None:
    primitive = _load("primitives.json")
    tolerance = _load("tolerances.json")
    close = {
        "atol": tolerance["absolute"],
        "rtol": tolerance["relative"],
    }

    pet = primitive["pet"]
    np.testing.assert_allclose(
        pet_from_temperature(**pet["inputs"]),
        pet["expected_mm_day"],
        **close,
    )

    water = primitive["water_balance"]
    np.testing.assert_allclose(
        daily_infiltration(**water["inputs"]),
        water["expected_daily_mm"],
        **close,
    )
    np.testing.assert_allclose(
        cumulative_infiltration(**water["inputs"]),
        water["expected_cumulative_mm"],
        **close,
    )

    passage = primitive["first_passage"]
    expected_passage = [
        np.nan if value is None else value
        for value in passage["expected_time"]
    ]
    np.testing.assert_allclose(
        first_passage_time(**passage["inputs"]),
        expected_passage,
        equal_nan=True,
        **close,
    )

    single = primitive["single_layer"]
    single_layer = _layer(single["layer"])
    np.testing.assert_allclose(
        cltf_pdf(single["y_mm"], single_layer),
        single["expected_pdf"],
        **close,
    )
    np.testing.assert_allclose(
        cltf_cdf(single["y_mm"], single_layer),
        single["expected_cdf"],
        **close,
    )

    two = primitive["two_layer"]
    np.testing.assert_allclose(
        cltf_layer_probabilities(
            two["y_mm"],
            _layer(two["top_layer"]),
            _layer(two["bottom_layer"]),
            method=two["method"],
            n_steps=two["n_steps"],
        ),
        two["expected_probabilities"],
        atol=(
            tolerance["trapezoid_absolute"]
            if two["method"] == "trapezoid"
            else tolerance["absolute"]
        ),
        rtol=tolerance["relative"],
    )

    concentration = primitive["concentration"]
    np.testing.assert_allclose(
        resident_concentration_ug_kg(**concentration["inputs"]),
        concentration["expected_ug_kg"],
        **close,
    )

    degradation = primitive["degradation"]
    np.testing.assert_allclose(
        apply_elapsed_degradation(**degradation["inputs"]),
        degradation["expected_fractions"],
        **close,
    )
