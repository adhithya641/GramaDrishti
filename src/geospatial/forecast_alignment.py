"""
GramDrishti — Coarse Forecast Grid Alignment
==============================================
Aligns 1 km metric grid cells to parent coarse weather forecast grid points.

Data Provenance Note:
  Historical forecast dataset status = STAND-IN (Open-Meteo Historical Forecast Archive).
  Preserves forecast_issue_time, valid_time, and lead_time.
  Does NOT perform spatial interpolation or baseline model fitting (Phase 3).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
from src.geospatial.crs_grid import UTM32643Transformer

logger = logging.getLogger("gramdrishti.geospatial.forecast_alignment")


def align_forecast_grid(
    grid_df: pd.DataFrame,
    forecast_csv_path: str | Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Map each 1 km grid cell centroid to its parent coarse forecast grid point.

    Parameters
    ----------
    grid_df : pd.DataFrame
        DataFrame with grid_id, centroid_x, centroid_y, latitude, longitude.
    forecast_csv_path : str | Path
        Path to Phase 1 historical forecast CSV file.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, Dict]
        - Grid DataFrame merged with forecast_parent_id column.
        - Forecast Parent Points summary DataFrame (forecast_parent_id, latitude, longitude, centroid_x, centroid_y).
        - Alignment diagnostics dictionary.
    """
    path = Path(forecast_csv_path)
    logger.info("Aligning 1 km grid to coarse forecast grid from %s...", path.name)

    if not path.exists():
        raise FileNotFoundError(f"Forecast dataset not found: {path}")

    fc_df = pd.read_csv(path)
    required = ["latitude", "longitude"]
    for col in required:
        if col not in fc_df.columns:
            raise KeyError(f"Missing required forecast field: {col}")

    # Extract unique forecast grid locations
    unique_fc_coords = fc_df[["latitude", "longitude"]].drop_duplicates().reset_index(drop=True)
    transformer = UTM32643Transformer()

    fc_parents = []
    for idx, row in unique_fc_coords.iterrows():
        lat, lon = float(row["latitude"]), float(row["longitude"])
        cx, cy = transformer.transform_to_utm(lon, lat)
        fc_parent_id = f"FC_GRID_{idx+1:02d}"
        fc_parents.append({
            "forecast_parent_id": fc_parent_id,
            "latitude": lat,
            "longitude": lon,
            "centroid_x": round(cx, 2),
            "centroid_y": round(cy, 2),
        })

    fc_parent_df = pd.DataFrame(fc_parents)
    logger.info("Identified %d unique coarse forecast grid points covering pilot region", len(fc_parent_df))

    # Map each 1 km cell centroid to nearest coarse forecast point in EPSG:32643 meters
    mapped_parents = []
    distances_to_fc = []

    for idx, row in grid_df.iterrows():
        cx, cy = row["centroid_x"], row["centroid_y"]

        # Vectorized Euclidean distance in projected meters
        dists = np.sqrt((fc_parent_df["centroid_x"] - cx)**2 + (fc_parent_df["centroid_y"] - cy)**2)
        min_idx = np.argmin(dists)
        best_parent_id = fc_parent_df.loc[min_idx, "forecast_parent_id"]
        best_dist = float(dists[min_idx])

        mapped_parents.append(best_parent_id)
        distances_to_fc.append(round(best_dist, 2))

    df_out = grid_df.copy()
    df_out["forecast_parent_id"] = mapped_parents
    df_out["distance_to_forecast_grid_m"] = distances_to_fc

    counts_per_parent = df_out["forecast_parent_id"].value_counts().to_dict()

    diagnostics = {
        "total_cells_mapped": len(df_out),
        "unique_forecast_parents": len(fc_parent_df),
        "cell_distribution_per_parent": counts_per_parent,
        "max_distance_to_forecast_m": float(max(distances_to_fc)),
        "mean_distance_to_forecast_m": float(np.mean(distances_to_fc)),
    }

    logger.info(
        "Forecast grid alignment complete: %d cells mapped across %d forecast points (mean distance %.1fm)",
        len(df_out), len(fc_parent_df), float(np.mean(distances_to_fc)),
    )

    return df_out, fc_parent_df, diagnostics
