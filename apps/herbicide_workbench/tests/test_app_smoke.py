#!/usr/bin/env python3
"""
Script: test_app_smoke.py
Objective: Verify the CLTF Streamlit workbench loads the NSW showcase by default.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
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
    assert "Residue assessment date" in [
        widget.label
        for widget in app.date_input
    ]
