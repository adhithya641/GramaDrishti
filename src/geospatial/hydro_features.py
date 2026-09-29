"""
GramDrishti — Hydrography Feature Engineering
===============================================
Calculates Euclidean distance to the nearest water body geometry (rivers, reservoirs, lakes)
for each 1 km metric grid cell in EPSG:32643 (meters).

Features calculated:
  - distance_to_nearest_water (meters)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Tuple
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape, MultiPolygon, Polygon
from src.geospatial.crs_grid import UTM32643Transformer

logger = logging.getLogger("gramdrishti.geospatial.hydro_features")


def compute_hydro_features(
    grid_df: pd.DataFrame,
    water_geojson_path: str | Path,
) -> pd.DataFrame:
    """
    Calculate Euclidean distance in meters to the nearest water body for each grid cell.

    Parameters
    ----------
    grid_df : pd.DataFrame
        DataFrame containing grid_id, centroid_x, centroid_y, latitude, longitude.
    water_geojson_path : str | Path
        Path to Phase 1 Water bodies GeoJSON file.

    Returns
    -------
    pd.DataFrame
        Original grid_df merged with distance_to_nearest_water column.
    """
    path = Path(water_geojson_path)
    logger.info("Computing water distance features from %s for %d grid cells...", path.name, len(grid_df))

    if not path.exists():
        raise FileNotFoundError(f"Water dataset not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        geojson = json.load(f)

    transformer = UTM32643Transformer()

    # Load water body geometries and transform coordinates to EPSG:32643 meters
    water_geoms_utm = []
    for feat in geojson.get("features", []):
        geom_wgs = shape(feat.get("geometry"))
        props = feat.get("properties", {})
        
        # Transform coords of geometry to EPSG:32643 meters
        if geom_wgs.geom_type == "Polygon":
            coords = [
                transformer.transform_to_utm(lon, lat)
                for lon, lat in geom_wgs.exterior.coords
            ]
            water_geoms_utm.append(Polygon(coords))
        elif geom_wgs.geom_type == "MultiPolygon":
            poly_list = []
            for poly in geom_wgs.geoms:
                coords = [
                    transformer.transform_to_utm(lon, lat)
                    for lon, lat in poly.exterior.coords
                ]
                poly_list.append(Polygon(coords))
            water_geoms_utm.append(MultiPolygon(poly_list))

    logger.info("Transformed %d water body geometries to EPSG:32643 meters", len(water_geoms_utm))

    distances = []
    for idx, row in grid_df.iterrows():
        cx, cy = row["centroid_x"], row["centroid_y"]
        pt = Point(cx, cy)

        if not water_geoms_utm:
            distances.append(99999.0)
            continue

        min_d = min(pt.distance(w_geom) for w_geom in water_geoms_utm)
        distances.append(round(float(min_d), 2))

    df_out = grid_df.copy()
    df_out["distance_to_nearest_water"] = distances

    logger.info(
        "Water distance calculation complete: min=%.1fm, max=%.1fm, mean=%.1fm",
        float(np.min(distances)), float(np.max(distances)), float(np.mean(distances)),
    )

    return df_out
