#!/usr/bin/env python3
"""
Script: maps.py
Objective: Build interactive pydeck maps for CLTF workbench site context.
Author: Yi Yu
Created: 2026-06-24
Last updated: 2026-06-24
Inputs: Shared site registry records and optional Mapbox tokens.
Outputs: pydeck Deck objects for Streamlit rendering.
Usage: Import build_site_map from workbench.maps.
Dependencies: pandas, pydeck
"""

from __future__ import annotations

import pandas as pd
import pydeck as pdk


SATELLITE_STYLE = "mapbox://styles/mapbox/satellite-streets-v12"
CARTO_POSITRON_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"


def _site_points(site: dict[str, object]) -> pd.DataFrame:
    site_latitude = float(site["latitude"])
    site_longitude = float(site["longitude"])
    silo_latitude = float(site.get("silo_latitude", site_latitude))
    silo_longitude = float(site.get("silo_longitude", site_longitude))
    return pd.DataFrame(
        [
            {
                "name": str(site.get("display_name", site["site_id"])),
                "type": "Selected site",
                "latitude": site_latitude,
                "longitude": site_longitude,
                "color": [122, 1, 119, 230],
                "radius_m": 75,
            },
            {
                "name": "Nearest SILO grid point",
                "type": "SILO grid",
                "latitude": silo_latitude,
                "longitude": silo_longitude,
                "color": [35, 139, 69, 220],
                "radius_m": 90,
            },
        ]
    )


def _line_points(points: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "from": [
                    float(points.loc[0, "longitude"]),
                    float(points.loc[0, "latitude"]),
                ],
                "to": [
                    float(points.loc[1, "longitude"]),
                    float(points.loc[1, "latitude"]),
                ],
                "name": "Site to SILO grid point",
            }
        ]
    )


def build_site_map(
    site: dict[str, object],
    mapbox_token: str | None = None,
) -> pdk.Deck:
    """Build an interactive site/SILO context map."""

    token = (mapbox_token or "").strip()
    points = _site_points(site)
    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=points,
            get_position="[longitude, latitude]",
            get_fill_color="color",
            get_radius="radius_m",
            pickable=True,
            stroked=True,
            filled=True,
            line_width_min_pixels=1,
            get_line_color=[255, 255, 255],
        ),
        pdk.Layer(
            "LineLayer",
            data=_line_points(points),
            get_source_position="from",
            get_target_position="to",
            get_color=[40, 40, 40, 180],
            get_width=2,
            pickable=False,
        ),
    ]
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=float(site["latitude"]),
            longitude=float(site["longitude"]),
            zoom=12,
            pitch=0,
            bearing=0,
        ),
        map_style=SATELLITE_STYLE if token else CARTO_POSITRON_STYLE,
        api_keys={"mapbox": token} if token else None,
        tooltip={
            "html": "<b>{type}</b><br/>{name}<br/>{latitude}, {longitude}",
            "style": {"backgroundColor": "#ffffff", "color": "#222222"},
        },
    )
