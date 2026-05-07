from __future__ import annotations

import sys

from workbench.config import REPO_ROOT, ensure_pyclt_path


def test_repo_root_points_to_pyclt_checkout():
    assert (REPO_ROOT / "pyclt" / "model.py").exists()


def test_config_does_not_hardcode_gadi_pyclt_checkout():
    config_source = (REPO_ROOT / "apps" / "herbicide_workbench" / "workbench" / "config.py").read_text()
    assert "/g/data/ym05/github/yuyi13/PyCLT" not in config_source


def test_ensure_pyclt_path_adds_repo_root():
    repo_text = str(REPO_ROOT)
    while repo_text in sys.path:
        sys.path.remove(repo_text)

    ensure_pyclt_path()

    assert sys.path[0] == repo_text
