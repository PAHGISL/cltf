#!/usr/bin/env python3
"""
Script: test_package.py
Objective: Verify Python CLTF package metadata and public imports.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Installed editable Python package.
Outputs: Pytest assertions.
Usage: python -m pytest python/tests/test_package.py -q
Dependencies: pytest, cltf
"""

import cltf


def test_package_version() -> None:
    assert cltf.__version__ == "0.1.0"
