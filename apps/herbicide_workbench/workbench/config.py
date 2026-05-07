"""Configuration helpers for the herbicide workbench."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PYCLT_ROOT = Path(os.environ.get("PYCLT_ROOT", REPO_ROOT))


def ensure_pyclt_path(pyclt_root: Path = DEFAULT_PYCLT_ROOT) -> None:
    """Make the active PyCLT source tree importable."""
    if not pyclt_root.exists():
        raise FileNotFoundError(f"PyCLT source tree was not found at {pyclt_root}")
    if not (pyclt_root / "pyclt").exists():
        raise FileNotFoundError(f"PyCLT package directory was not found under {pyclt_root}")
    root_text = str(pyclt_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
