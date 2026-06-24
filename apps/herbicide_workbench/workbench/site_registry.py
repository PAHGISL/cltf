#!/usr/bin/env python3
"""
Script: site_registry.py
Objective: Expose shared NSW and SA CLTF site/case inputs to the workbench.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: examples/data/sites.json and per-case case.json files.
Outputs: Site dictionaries, case selections, and input-directory paths.
Usage: Import registry helpers from workbench.site_registry.
Dependencies: json, pathlib, workbench.config, workbench.contracts
"""

from __future__ import annotations

import json
from pathlib import Path

from workbench.config import EXAMPLES_DATA
from workbench.contracts import CaseSelection


CASE_DIRECTORIES = {
    ("NSW_Griffith", "Heavy", "Imazapic"): "nsw_griffith_heavy_imazapic",
    ("SA_Minnipa", "Heavy", "Imazapic"): "sa_minnipa_heavy_imazapic",
}


def load_site_registry() -> list[dict[str, object]]:
    """Load the shared CLTF site registry."""

    path = EXAMPLES_DATA / "sites.json"
    if not path.exists():
        raise FileNotFoundError(f"Shared site registry does not exist: {path}")
    sites = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(sites, list):
        raise ValueError("Shared site registry must be a list of site records")
    return sites


def get_site(site_id: str) -> dict[str, object]:
    """Return one site registry record by site identifier."""

    matches = [site for site in load_site_registry() if site["site_id"] == site_id]
    if len(matches) != 1:
        raise KeyError(f"Unknown shared site_id: {site_id}")
    return dict(matches[0])


def available_soils(site_id: str) -> list[str]:
    """Return configured soil groups for a site."""

    site = get_site(site_id)
    return [str(value) for value in site.get("soil_groups", [])]


def available_herbicides(site_id: str, soil_group: str) -> list[str]:
    """Return herbicides with shared case inputs for a site and soil group."""

    herbicides = sorted(
        herbicide
        for (case_site, case_soil, herbicide), directory in CASE_DIRECTORIES.items()
        if case_site == site_id
        and case_soil == soil_group
        and (EXAMPLES_DATA / directory / "case.json").exists()
    )
    if herbicides:
        return herbicides
    site = get_site(site_id)
    default = str(site.get("default_herbicide", ""))
    return [default] if default else []


def default_case(
    registry: list[dict[str, object]] | None = None,
) -> CaseSelection:
    """Return the approved default showcase case."""

    sites = registry if registry is not None else load_site_registry()
    if not sites:
        raise ValueError("Site registry is empty")
    preferred = next(
        (site for site in sites if site["site_id"] == "NSW_Griffith"),
        sites[0],
    )
    return CaseSelection(
        site_id=str(preferred["site_id"]),
        soil_group=str(preferred.get("default_soil_group", "Heavy")),
        herbicide=str(preferred.get("default_herbicide", "Imazapic")),
    )


def case_input_dir(case: CaseSelection) -> Path:
    """Return the shared input directory for a case selection."""

    key = (case.site_id, case.soil_group, case.herbicide)
    try:
        directory = CASE_DIRECTORIES[key]
    except KeyError as error:
        raise KeyError(f"No shared case inputs are available for {case}") from error
    path = EXAMPLES_DATA / directory
    if not path.exists():
        raise FileNotFoundError(f"Shared case input directory does not exist: {path}")
    return path
