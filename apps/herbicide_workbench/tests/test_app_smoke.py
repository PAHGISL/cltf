#!/usr/bin/env python3
"""
Script: test_app_smoke.py
Objective: Verify the CLTF Streamlit workbench loads the NSW showcase by default.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-25
Inputs: apps/herbicide_workbench/app.py.
Outputs: Streamlit AppTest smoke assertions.
Usage: python -m pytest apps/herbicide_workbench/tests/test_app_smoke.py -q
Dependencies: streamlit, workbench
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_default_app_loads_nsw_showcase() -> None:
    app = AppTest.from_file("apps/herbicide_workbench/app.py").run(timeout=30)

    assert not app.exception
    assert app.selectbox[0].value == "NSW Griffith"
    assert app.selectbox[3].options == [
        "30 days beyond application",
        "60 days beyond application",
        "90 days beyond application",
        "180 days beyond application",
        "270 days beyond application",
        "360 days beyond application",
        "Custom",
    ]
    assert "Residue assessment date" in [
        widget.label
        for widget in app.date_input
    ]


def test_default_app_run_generates_diagnostics() -> None:
    app = AppTest.from_file("apps/herbicide_workbench/app.py").run(timeout=30)
    app.button[0].click().run(timeout=120)

    assert not app.exception
    assert "CLTF diagnostic plots" in [
        element.value
        for element in app.subheader
    ]
    assert "Predictions" in [
        element.value
        for element in app.subheader
    ]
