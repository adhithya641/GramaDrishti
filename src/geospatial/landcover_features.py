"""
GramDrishti — Land Cover Feature Engineering
==============================================
Calculates Land Use / Land Cover (LULC) class fractions and dominant class
for each 1 km metric grid cell from the 10m LULC raster.

LULC Legend (ESA WorldCover standard):
  - 10: Tree cover
  - 20: Shrubland
  - 30: Grassland
  - 40: Cropland
  - 50: Built-up
  - 80: Permanent Water Bodies
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple
import numpy as np
import pandas as pd
import tifffile

logger = logging.getLogger("gramdrishti.geospatial.landcover_features")

LULC_CLASS_MAP = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    80: "Water",
}


def compute_landcover_features(
    grid_df: pd.DataFrame,
    landcover_tif_path: str | Path,
) -> pd.DataFrame:
    """
    Extract LULC class fractions and dominant class for each 1 km grid cell.

    Parameters
    ----------
    grid_df : pd.DataFrame
        DataFrame with grid_id, latitude, longitude.
    landcover_tif_path : str | Path
        Path to Phase 1 Land Cover GeoTIFF raster.

    Returns
    -------
    pd.DataFrame
        Original grid_df merged with LULC fraction features.
    """
    path = Path(landcover_tif_path)
    logger.info("Computing Land Cover features from %s for %d grid cells...", path.name, len(grid_df))

    # Read LULC array
    with tifffile.TiffFile(path) as tf:
        lc_array = tf.asarray()
        if lc_array.ndim == 3:
            lc_array = lc_array[0]

    rows, cols = lc_array.shape
    unique_classes = np.unique(lc_array)
    logger.info("LULC raster dimensions: %dx%d pixels, unique classes found: %s",
                cols, rows, list(unique_classes))

    # Geographic bounding box matching Coimbatore pilot region
    min_lon, max_lon = 76.60, 77.30
    min_lat, max_lat = 10.20, 11.40

    dominant_classes = []
    frac_tree = []
    frac_shrub = []
    frac_grass = []
    frac_cropland = []
    frac_builtup = []
    frac_water = []
    frac_nodata = []

    for idx, row in grid_df.iterrows():
        lat, lon = row["latitude"], row["longitude"]

        # Map cell centroid (lon, lat) to LULC pixel indices
        col_idx = int(((lon - min_lon) / (max_lon - min_lon)) * cols)
        row_idx = int(((max_lat - lat) / (max_lat - min_lat)) * rows)

        col_idx = np.clip(col_idx, 0, cols - 1)
        row_idx = np.clip(row_idx, 0, rows - 1)

        # Extract 10x10 pixel footprint window
        r_start = max(0, row_idx - 5)
        r_end = min(rows, row_idx + 6)
        c_start = max(0, col_idx - 5)
        c_end = min(cols, col_idx + 6)

        sub_lc = lc_array[r_start:r_end, c_start:c_end]
        total_px = sub_lc.size

        if total_px == 0:
            dominant_classes.append("Cropland")
            frac_tree.append(0.0)
            frac_shrub.append(0.0)
            frac_grass.append(0.0)
            frac_cropland.append(1.0)
            frac_builtup.append(0.0)
            frac_water.append(0.0)
            frac_nodata.append(0.0)
            continue

        # Count frequencies
        vals, counts = np.unique(sub_lc, return_counts=True)
        counts_dict = dict(zip(vals, counts))

        # Dominant class
        dom_val = vals[np.argmax(counts)]
        dom_name = LULC_CLASS_MAP.get(dom_val, f"Class_{dom_val}")
        dominant_classes.append(dom_name)

        # Class fractions
        f_tree = round(float(counts_dict.get(10, 0) / total_px), 4)
        f_shrub = round(float(counts_dict.get(20, 0) / total_px), 4)
        f_grass = round(float(counts_dict.get(30, 0) / total_px), 4)
        f_crop = round(float(counts_dict.get(40, 0) / total_px), 4)
        f_built = round(float(counts_dict.get(50, 0) / total_px), 4)
        f_water = round(float(counts_dict.get(80, 0) / total_px), 4)
        f_no = round(float(1.0 - (f_tree + f_shrub + f_grass + f_crop + f_built + f_water)), 4)
        f_no = max(0.0, f_no)

        frac_tree.append(f_tree)
        frac_shrub.append(f_shrub)
        frac_grass.append(f_grass)
        frac_cropland.append(f_crop)
        frac_builtup.append(f_built)
        frac_water.append(f_water)
        frac_nodata.append(f_no)

    df_out = grid_df.copy()
    df_out["dominant_landcover_class"] = dominant_classes
    df_out["landcover_fraction_tree"] = frac_tree
    df_out["landcover_fraction_shrub"] = frac_shrub
    df_out["landcover_fraction_grass"] = frac_grass
    df_out["landcover_fraction_cropland"] = frac_cropland
    df_out["landcover_fraction_builtup"] = frac_builtup
    df_out["landcover_fraction_water"] = frac_water
    df_out["nodata_fraction"] = frac_nodata

    logger.info("Land Cover feature engineering complete: %s dominant class distribution",
                df_out["dominant_landcover_class"].value_counts().to_dict())

    return df_out
