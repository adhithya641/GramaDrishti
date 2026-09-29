"""
GramDrishti — Spatial & Temporal Alignment Engine
===================================================
Performs deterministic timestamp matching (observation timestamp == forecast valid_time)
and spatial alignment (station -> 1 km grid_id -> panchayat_id -> forecast_parent_id).

Assigned Chronological Splits:
  - TRAIN: 2024-01-01 to 2024-03-31
  - CALIBRATION: 2024-04-01 to 2024-04-30
  - TEST: 2024-05-01 to 2024-06-30
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
from src.geospatial.crs_grid import UTM32643Transformer

logger = logging.getLogger("gramdrishti.matchups.spatial_temporal_matcher")


def match_observations_and_forecasts(
    obs_df: pd.DataFrame,
    fc_df: pd.DataFrame,
    master_grid_csv_path: str | Path,
    config: Dict,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Perform temporal and spatial alignment between station observations and forecasts.

    Parameters
    ----------
    obs_df : pd.DataFrame
        Loaded observation DataFrame.
    fc_df : pd.DataFrame
        Loaded forecast DataFrame.
    master_grid_csv_path : str | Path
        Path to Phase 2 geospatial master feature CSV file.
    config : Dict
        Configuration dictionary (from configs/baselines.yaml).

    Returns
    -------
    Tuple[pd.DataFrame, Dict]
        Aligned matchup DataFrame and matching statistics dictionary.
    """
    logger.info("Matching %d observation records with %d forecast records...", len(obs_df), len(fc_df))

    grid_path = Path(master_grid_csv_path)
    if not grid_path.exists():
        raise FileNotFoundError(f"Geospatial master grid CSV not found: {grid_path}")

    grid_master = pd.read_csv(grid_path)
    transformer = UTM32643Transformer()

    # Step 1: Spatial alignment of weather stations to 1 km grid, panchayats, and forecast parents
    unique_stations = obs_df[["station_id", "latitude", "longitude", "station_elevation"]].drop_duplicates().reset_index(drop=True)
    
    stn_mappings = {}
    stn_groups = {}
    for idx, stn in unique_stations.iterrows():
        stn_id = stn["station_id"]
        slat, slon = stn["latitude"], stn["longitude"]
        sx, sy = transformer.transform_to_utm(slon, slat)

        # Nearest 1 km grid cell in EPSG:32643 meters
        dists = np.sqrt((grid_master["centroid_x"] - sx)**2 + (grid_master["centroid_y"] - sy)**2)
        best_idx = np.argmin(dists)
        best_cell = grid_master.iloc[best_idx]

        stn_mappings[stn_id] = {
            "grid_id": best_cell["grid_id"],
            "panchayat_id": best_cell["panchayat_id"],
            "panchayat_name": best_cell["panchayat_name"],
            "forecast_parent_id": best_cell["forecast_parent_id"],
            "grid_elevation": best_cell["elevation_mean"],
            "station_utm_x": sx,
            "station_utm_y": sy,
        }
        # Assign station_group key for future Leave-One-Station-Out (LOSO) cross-validation
        stn_groups[stn_id] = f"GROUP_{stn_id}"

    # Assign forecast_parent_id to forecast records based on latitude/longitude
    unique_fc = fc_df[["latitude", "longitude"]].drop_duplicates().reset_index(drop=True)
    unique_fc["forecast_parent_id"] = [f"FC_GRID_{i+1:02d}" for i in range(len(unique_fc))]
    fc_df_with_parent = pd.merge(fc_df, unique_fc, on=["latitude", "longitude"], suffixes=("", "_unique"))

    # Assign assigned forecast_parent_id to obs_df
    obs_df["forecast_parent_id"] = obs_df["station_id"].map(lambda sid: stn_mappings[sid]["forecast_parent_id"])

    # Step 2: Temporal & Spatial alignment (timestamp == valid_time AND station forecast_parent_id == forecast_parent_id)
    merged = pd.merge(
        obs_df,
        fc_df_with_parent,
        left_on=["timestamp", "forecast_parent_id"],
        right_on=["valid_time", "forecast_parent_id"],
        suffixes=("_obs", "_fc"),
    )

    if merged.empty:
        raise ValueError("Temporal alignment produced 0 matches. Verify timestamp formats in observations and forecasts.")

    # Attach spatial alignment metadata
    grid_ids = [stn_mappings[sid]["grid_id"] for sid in merged["station_id"]]
    p_ids = [stn_mappings[sid]["panchayat_id"] for sid in merged["station_id"]]
    p_names = [stn_mappings[sid]["panchayat_name"] for sid in merged["station_id"]]
    grid_elevs = [stn_mappings[sid]["grid_elevation"] for sid in merged["station_id"]]
    s_groups = [stn_groups[sid] for sid in merged["station_id"]]

    merged["grid_id"] = grid_ids
    merged["panchayat_id"] = p_ids
    merged["panchayat_name"] = p_names
    merged["grid_elevation"] = grid_elevs
    merged["station_group"] = s_groups
    merged["observation_time"] = merged["timestamp"]


    # Step 3: Chronological temporal split assignment (TRAIN / CALIBRATION / TEST)
    splits = []
    splits_cfg = config.get("temporal_splits", {})
    train_end = pd.to_datetime(splits_cfg.get("train", {}).get("end_date", "2024-03-31 23:59:59"))
    cal_end = pd.to_datetime(splits_cfg.get("calibration", {}).get("end_date", "2024-04-30 23:59:59"))

    for dt in merged["observation_time"]:
        if dt <= train_end:
            splits.append("TRAIN")
        elif dt <= cal_end:
            splits.append("CALIBRATION")
        else:
            splits.append("TEST")

    merged["split"] = splits

    split_counts = merged["split"].value_counts().to_dict()
    lead_dist = merged["lead_time_hours"].value_counts().to_dict()

    stats = {
        "total_matched_records": len(merged),
        "unique_stations": merged["station_id"].nunique(),
        "date_range": [str(merged["observation_time"].min()), str(merged["observation_time"].max())],
        "split_counts": split_counts,
        "lead_time_distribution": lead_dist,
    }

    logger.info(
        "Observation ↔ Forecast matching complete: %d records matched across %d stations. Splits: %s",
        len(merged), merged["station_id"].nunique(), split_counts,
    )

    return merged, stats
