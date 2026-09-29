"""
GramDrishti — Panchayat Spatial Assignment
============================================
Spatially assigns 1 km metric grid cells to corresponding Gram Panchayats in Coimbatore District.

Rule:
  1. Primary rule: Point-in-polygon assignment of cell centroid (lon, lat) inside Gram Panchayat polygon.
  2. Fallback rule: Spatial distance / nearest Gram Panchayat centroid if cell centroid lies on a boundary gap.

Diagnostics produced:
  - Total cells assigned to a Panchayat
  - Unassigned / boundary cells handled
  - Panchayats with zero assigned grid cells
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape, MultiPolygon, Polygon

logger = logging.getLogger("gramdrishti.geospatial.panchayat_assignment")


def assign_panchayats(
    grid_df: pd.DataFrame,
    panchayats_geojson_path: str | Path,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Assign Gram Panchayat administrative identifiers to grid cells.

    Parameters
    ----------
    grid_df : pd.DataFrame
        DataFrame containing grid_id, latitude, longitude, centroid_x, centroid_y.
    panchayats_geojson_path : str | Path
        Path to Phase 1 Panchayat boundary GeoJSON file.

    Returns
    -------
    Tuple[pd.DataFrame, Dict]
        Updated grid_df with panchayat fields added, and a dictionary of assignment diagnostics.
    """
    logger.info("Assigning Gram Panchayats for %d grid cells...", len(grid_df))
    path = Path(panchayats_geojson_path)
    if not path.exists():
        raise FileNotFoundError(f"Panchayat boundaries file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    # Load Panchayat features and Shapely geometries
    panchayats = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        geom = shape(feat.get("geometry"))
        panchayats.append({
            "panchayat_code": props.get("panchayat_code", "UNKNOWN_GP"),
            "panchayat_name": props.get("panchayat_name", "UNKNOWN"),
            "block_name": props.get("block_name", "UNKNOWN"),
            "district_name": props.get("district_name", "Coimbatore"),
            "geometry": geom,
            "centroid": geom.centroid,
        })

    logger.info("Loaded %d Gram Panchayat boundary polygons", len(panchayats))

    # Perform assignment per cell
    p_codes = []
    p_names = []
    b_names = []
    d_names = []
    assignment_modes = []

    assigned_count = 0
    boundary_fallback_count = 0

    for idx, row in grid_df.iterrows():
        pt = Point(row["longitude"], row["latitude"])
        found = False

        # Primary Rule: Centroid point inside Panchayat polygon
        for p in panchayats:
            if p["geometry"].contains(pt) or p["geometry"].intersects(pt):
                p_codes.append(p["panchayat_code"])
                p_names.append(p["panchayat_name"])
                b_names.append(p["block_name"])
                d_names.append(p["district_name"])
                assignment_modes.append("centroid_contains")
                assigned_count += 1
                found = True
                break

        # Fallback Rule: Nearest Panchayat centroid if outside all polygons
        if not found:
            min_dist = float("inf")
            best_p = None
            for p in panchayats:
                d = pt.distance(p["centroid"])
                if d < min_dist:
                    min_dist = d
                    best_p = p
            if best_p is not None:
                p_codes.append(best_p["panchayat_code"])
                p_names.append(best_p["panchayat_name"])
                b_names.append(best_p["block_name"])
                d_names.append(best_p["district_name"])
                assignment_modes.append("nearest_fallback")
                boundary_fallback_count += 1
            else:
                p_codes.append("GP_UNKNOWN")
                p_names.append("Unknown Panchayat")
                b_names.append("Unknown Block")
                d_names.append("Coimbatore")
                assignment_modes.append("unassigned")

    # Update DataFrame
    df_out = grid_df.copy()
    df_out["panchayat_id"] = p_codes
    df_out["panchayat_name"] = p_names
    df_out["block_name"] = b_names
    df_out["district_name"] = d_names
    df_out["assignment_mode"] = assignment_modes

    # Calculate Diagnostics
    counts_per_gp = df_out["panchayat_name"].value_counts().to_dict()
    all_gp_names = set(p["panchayat_name"] for p in panchayats)
    assigned_gp_names = set(df_out["panchayat_name"].unique())
    zero_cell_gps = list(all_gp_names - assigned_gp_names)

    diagnostics = {
        "total_cells": len(grid_df),
        "assigned_centroid_contains": assigned_count,
        "assigned_nearest_fallback": boundary_fallback_count,
        "total_panchayats_in_layer": len(all_gp_names),
        "panchayats_with_cells": len(assigned_gp_names),
        "panchayats_with_zero_cells": zero_cell_gps,
        "zero_cell_count": len(zero_cell_gps),
    }

    logger.info(
        "Panchayat assignment complete: %d cells assigned (centroid), %d fallback, %d Panchayats represented, %d zero-cell Panchayats",
        assigned_count, boundary_fallback_count, len(assigned_gp_names), len(zero_cell_gps),
    )

    return df_out, diagnostics
