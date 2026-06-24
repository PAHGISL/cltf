#!/usr/bin/env python3
"""
Script: config.py
Objective: Configure repository paths for the CLTF Streamlit workbench.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Repository-relative app and Python package paths.
Outputs: Import-path helper for the Python cltf package.
Usage: Call ensure_cltf_path() before importing cltf from app entry points.
Dependencies: pathlib, sys
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CLTF_SRC = REPO_ROOT / "python" / "src"
EXAMPLES_DATA = REPO_ROOT / "examples" / "data"


def ensure_cltf_path() -> None:
    """Make the active Python CLTF source tree importable."""

    if not (CLTF_SRC / "cltf" / "__init__.py").exists():
        raise FileNotFoundError(f"Python CLTF source was not found at {CLTF_SRC}")
    src_text = str(CLTF_SRC)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)
