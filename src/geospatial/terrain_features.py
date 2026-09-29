"""
GramDrishti — Terrain Feature Engineering
===========================================
Calculates continuous terrain features from the 30m Digital Elevation Model (DEM)
for every 1 km metric grid cell covering the Coimbatore pilot region.

Features calculated per 1 km grid cell:
  - elevation_mean, elevation_std, elevation_min, elevation_max, elevation_range
  - slope_mean, slope_std, slope_min, slope_max (degrees, Horn 3x3 gradient)
  - aspect_sin, aspect_cos, aspect_mean_deg (trigonometric aspect representation)
  - tri_mean, tri_std (Riley et al. 1999 Terrain Ruggedness Index)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
import tifffile

logger = logging.getLogger("gramdrishti.geospatial.terrain_features")


def _compute_dem_derivatives(dem_array: np.ndarray, cell_res_m: float = 30.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute slope, aspect, and TRI arrays from a 2D DEM elevation matrix.

    Parameters
    ----------
    dem_array : np.ndarray
        2D float array of elevation values in meters.
    cell_res_m : float
        Pixel size in meters (30.0m for 1 arc-second DEM).

    Returns
    -------
    Tuple[np.ndarray, np.ndarray, np.ndarray]
        (slope_deg, aspect_deg, tri_array)
    """
    rows, cols = dem_array.shape
    slope_deg = np.zeros((rows, cols), dtype=np.float32)
    aspect_deg = np.zeros((rows, cols), dtype=np.float32)
    tri_array = np.zeros((rows, cols), dtype=np.float32)

    # Pad array for 3x3 window calculations
    padded = np.pad(dem_array, pad_width=1, mode="edge")

    # Horn 3x3 finite-difference kernels for dz/dx and dz/dy
    for r in range(rows):
        for c in range(cols):
            # 3x3 neighborhood window around cell (r+1, c+1) in padded matrix
            w = padded[r:r+3, c:c+3]
            z_center = w[1, 1]

            # Horn's 3x3 finite differences
            dz_dx = ((w[0, 2] + 2.0 * w[1, 2] + w[2, 2]) - (w[0, 0] + 2.0 * w[1, 0] + w[2, 0])) / (8.0 * cell_res_m)
            dz_dy = ((w[2, 0] + 2.0 * w[2, 1] + w[2, 2]) - (w[0, 0] + 2.0 * w[0, 1] + w[0, 2])) / (8.0 * cell_res_m)

            # Slope in degrees
            slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
            s_deg = np.degrees(slope_rad)
            slope_deg[r, c] = s_deg

            # Aspect in degrees [0, 360)
            if s_deg < 0.1:
                # Flat terrain -> aspect undefined / 0
                aspect_deg[r, c] = 0.0
            else:
                a_rad = np.arctan2(-dz_dy, dz_dx)
                a_deg = np.degrees(a_rad) % 360.0
                aspect_deg[r, c] = a_deg

            # Riley et al. (1999) Terrain Ruggedness Index (TRI)
            # TRI = sqrt( sum( (z_ij - z_00)^2 ) ) over 3x3 neighborhood
            tri_val = np.sqrt(np.sum((w - z_center)**2))
            tri_array[r, c] = tri_val

    return slope_deg, aspect_deg, tri_array


def compute_terrain_features(
    grid_df: pd.DataFrame,
    dem_tif_path: str | Path,
) -> pd.DataFrame:
    """
    Extract and calculate elevation, slope, aspect, and TRI features for each 1 km grid cell.

    Parameters
    ----------
    grid_df : pd.DataFrame
        DataFrame with grid_id, min_x, max_x, min_y, max_y, latitude, longitude.
    dem_tif_path : str | Path
        Path to Phase 1 DEM GeoTIFF.

    Returns
    -------
    pd.DataFrame
        Original grid_df merged with all terrain features.
    """
    path = Path(dem_tif_path)
    logger.info("Computing terrain features from DEM %s for %d grid cells...", path.name, len(grid_df))

    # Read DEM array using tifffile
    with tifffile.TiffFile(path) as tf:
        dem_array = tf.asarray()
        if dem_array.ndim == 3:
            dem_array = dem_array[0]
        dem_array = dem_array.astype(np.float32)

    rows, cols = dem_array.shape
    logger.info("DEM raster dimensions: %dx%d pixels, min elev=%.1fm, max elev=%.1fm",
                cols, rows, float(np.min(dem_array)), float(np.max(dem_array)))

    # Compute DEM derivatives (slope, aspect, TRI)
    slope_arr, aspect_arr, tri_arr = _compute_dem_derivatives(dem_array, cell_res_m=30.0)

    # Grid mapping parameters matching Coimbatore pilot DEM extent
    # min_lon: 76.60, max_lon: 77.30, min_lat: 10.20, max_lat: 11.40
    min_lon, max_lon = 76.60, 77.30
    min_lat, max_lat = 10.20, 11.40

    elev_means, elev_stds, elev_mins, elev_maxs, elev_ranges = [], [], [], [], []
    slope_means, slope_stds, slope_mins, slope_maxs = [], [], [], []
    aspect_sins, aspect_coss, aspect_means = [], [], []
    tri_means, tri_stds = [], []

    for idx, row in grid_df.iterrows():
        lat, lon = row["latitude"], row["longitude"]

        # Map cell centroid (lon, lat) to DEM pixel indices
        col_idx = int(((lon - min_lon) / (max_lon - min_lon)) * cols)
        row_idx = int(((max_lat - lat) / (max_lat - min_lat)) * rows)

        col_idx = np.clip(col_idx, 0, cols - 1)
        row_idx = np.clip(row_idx, 0, rows - 1)

        # Extract 10x10 pixel window (~300m x 300m to 1km footprint sample)
        r_start = max(0, row_idx - 5)
        r_end = min(rows, row_idx + 6)
        c_start = max(0, col_idx - 5)
        c_end = min(cols, col_idx + 6)

        sub_elev = dem_array[r_start:r_end, c_start:c_end]
        sub_slope = slope_arr[r_start:r_end, c_start:c_end]
        sub_aspect = aspect_arr[r_start:r_end, c_start:c_end]
        sub_tri = tri_arr[r_start:r_end, c_start:c_end]

        # Elevation stats
        e_mean = float(np.mean(sub_elev))
        e_std = float(np.std(sub_elev))
        e_min = float(np.min(sub_elev))
        e_max = float(np.max(sub_elev))
        e_rng = e_max - e_min

        # Slope stats
        s_mean = float(np.mean(sub_slope))
        s_std = float(np.std(sub_slope))
        s_min = float(np.min(sub_slope))
        s_max = float(np.max(sub_slope))

        # Aspect stats & continuous trigonometric representation
        asp_rad = np.radians(sub_aspect)
        asp_sin = float(np.mean(np.sin(asp_rad)))
        asp_cos = float(np.mean(np.cos(asp_rad)))
        asp_mean = float(np.mean(sub_aspect))

        # TRI stats
        t_mean = float(np.mean(sub_tri))
        t_std = float(np.std(sub_tri))

        elev_means.append(round(e_mean, 2))
        elev_stds.append(round(e_std, 2))
        elev_mins.append(round(e_min, 2))
        elev_maxs.append(round(e_max, 2))
        elev_ranges.append(round(e_rng, 2))

        slope_means.append(round(s_mean, 2))
        slope_stds.append(round(s_std, 2))
        slope_mins.append(round(s_min, 2))
        slope_maxs.append(round(s_max, 2))

        aspect_sins.append(round(asp_sin, 4))
        aspect_coss.append(round(asp_cos, 4))
        aspect_means.append(round(asp_mean, 2))

        tri_means.append(round(t_mean, 2))
        tri_stds.append(round(t_std, 2))

    df_out = grid_df.copy()
    df_out["elevation_mean"] = elev_means
    df_out["elevation_std"] = elev_stds
    df_out["elevation_min"] = elev_mins
    df_out["elevation_max"] = elev_maxs
    df_out["elevation_range"] = elev_ranges

    df_out["slope_mean"] = slope_means
    df_out["slope_std"] = slope_stds
    df_out["slope_min"] = slope_mins
    df_out["slope_max"] = slope_maxs

    df_out["aspect_sin"] = aspect_sins
    df_out["aspect_cos"] = aspect_coss
    df_out["aspect_mean_deg"] = aspect_means

    df_out["tri_mean"] = tri_means
    df_out["tri_std"] = tri_stds

    logger.info(
        "Terrain feature engineering complete: elevation range %.1fm-%.1fm, slope range %.1f°-%.1f°, TRI range %.1f-%.1f",
        min(elev_mins), max(elev_maxs), min(slope_mins), max(slope_maxs), min(tri_means), max(tri_means),
    )

    return df_out
