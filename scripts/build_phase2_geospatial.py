"""
GramDrishti — Phase 2 Geospatial Grid & Feature Engineering Pipeline
======================================================================
Reproducible entry point for generating the 1 km metric grid and extracting
terrain/GIS features for the Coimbatore pilot region (Tamil Nadu).

Execution Steps:
  1. Load Phase 1 validated geospatial layers
  2. Select projected metric CRS: EPSG:32643 (UTM Zone 43N)
  3. Generate 1 km x 1 km regular grid
  4. Perform spatial Panchayat assignment
  5. Extract DEM elevation features
  6. Extract Slope features (Horn's 3x3 algorithm)
  7. Extract Aspect features (trigonometric sin/cos)
  8. Extract Terrain Ruggedness Index (Riley et al. 1999 TRI)
  9. Extract Land Cover class fractions & dominant class
 10. Calculate distance to nearest water body (in meters)
 11. Map grid cells to parent coarse forecast grid points
 12. Save processed geospatial datasets under data/processed/geospatial/
 13. Execute Quality Checks A through O
"""

import json
import logging
import os
import sys
from pathlib import Path
import pandas as pd

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.geospatial.crs_grid import generate_1km_grid, TARGET_CRS_NAME
from src.geospatial.panchayat_assignment import assign_panchayats
from src.geospatial.terrain_features import compute_terrain_features
from src.geospatial.landcover_features import compute_landcover_features
from src.geospatial.hydro_features import compute_hydro_features
from src.geospatial.forecast_alignment import align_forecast_grid
from src.geospatial.validate_grid import GridValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gramdrishti.phase2_build")


def main():
    logger.info("=========================================================")
    logger.info(" GramDrishti — Phase 2 Geospatial Grid Feature Build ")
    logger.info("=========================================================")
    logger.info("Projected CRS Selected: %s", TARGET_CRS_NAME)

    raw_dir = PROJECT_ROOT / "data" / "raw"
    proc_dir = PROJECT_ROOT / "data" / "processed"
    geo_proc_dir = proc_dir / "geospatial"
    meta_dir = PROJECT_ROOT / "data" / "metadata"

    geo_proc_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Step 1: Generate 1 km Metric Grid
    # -----------------------------------------------------------------------
    logger.info("Step 1/7: Generating 1 km metric grid in EPSG:32643...")
    grid_df = generate_1km_grid(
        min_lat=10.20, max_lat=11.40, min_lon=76.60, max_lon=77.30
    )

    # -----------------------------------------------------------------------
    # Step 2: Assign Gram Panchayats
    # -----------------------------------------------------------------------
    logger.info("Step 2/7: Assigning Gram Panchayats...")
    panchayats_path = raw_dir / "boundaries" / "coimbatore_panchayats.geojson"
    grid_df, p_diag = assign_panchayats(grid_df, panchayats_path)

    # -----------------------------------------------------------------------
    # Step 3: Compute DEM & Terrain Features (Elevation, Slope, Aspect, TRI)
    # -----------------------------------------------------------------------
    logger.info("Step 3/7: Computing DEM, Slope, Aspect, and TRI features...")
    dem_path = raw_dir / "dem" / "coimbatore_dem_30m.tif"
    grid_df = compute_terrain_features(grid_df, dem_path)

    # -----------------------------------------------------------------------
    # Step 4: Compute Land Cover Features
    # -----------------------------------------------------------------------
    logger.info("Step 4/7: Computing Land Cover class fractions...")
    lc_path = raw_dir / "landcover" / "coimbatore_landcover_10m.tif"
    grid_df = compute_landcover_features(grid_df, lc_path)

    # -----------------------------------------------------------------------
    # Step 5: Compute Water Distance Features
    # -----------------------------------------------------------------------
    logger.info("Step 5/7: Computing Distance to Water...")
    water_path = raw_dir / "water" / "coimbatore_water_bodies.geojson"
    grid_df = compute_hydro_features(grid_df, water_path)

    # -----------------------------------------------------------------------
    # Step 6: Map Coarse Forecast Parent Grid Points
    # -----------------------------------------------------------------------
    logger.info("Step 6/7: Aligning Coarse Forecast Grid Points...")
    forecast_path = raw_dir / "forecasts" / "coimbatore_historical_forecasts.csv"
    grid_df, fc_parents_df, fc_diag = align_forecast_grid(grid_df, forecast_path)

    # -----------------------------------------------------------------------
    # Step 7: Save Processed Outputs & Run Quality Assurance
    # -----------------------------------------------------------------------
    logger.info("Step 7/7: Saving processed geospatial datasets and validating Quality Checks A-O...")

    # Extract component feature tables preserving grid_id
    terrain_cols = [
        "grid_id", "elevation_mean", "elevation_std", "elevation_min", "elevation_max", "elevation_range",
        "slope_mean", "slope_std", "slope_min", "slope_max", "aspect_sin", "aspect_cos", "aspect_mean_deg",
        "tri_mean", "tri_std"
    ]
    landcover_cols = [
        "grid_id", "dominant_landcover_class", "landcover_fraction_tree", "landcover_fraction_shrub",
        "landcover_fraction_grass", "landcover_fraction_cropland", "landcover_fraction_builtup",
        "landcover_fraction_water", "nodata_fraction"
    ]
    hydro_cols = ["grid_id", "distance_to_nearest_water"]
    forecast_map_cols = ["grid_id", "forecast_parent_id", "distance_to_forecast_grid_m"]

    # Exclude Shapely polygon geometry object from CSV exports
    csv_master = grid_df.drop(columns=["geometry"])

    # Save CSV outputs
    csv_master.to_csv(geo_proc_dir / "geospatial_features_master.csv", index=False)
    csv_master.to_csv(geo_proc_dir / "grid_1km.csv", index=False)
    grid_df[terrain_cols].to_csv(geo_proc_dir / "terrain_features.csv", index=False)
    grid_df[landcover_cols].to_csv(geo_proc_dir / "landcover_features.csv", index=False)
    grid_df[hydro_cols].to_csv(geo_proc_dir / "hydro_features.csv", index=False)
    grid_df[forecast_map_cols].to_csv(geo_proc_dir / "forecast_grid_mapping.csv", index=False)

    # Save GeoJSON output for GIS visualization
    geojson_features = []
    for idx, row in grid_df.iterrows():
        poly = row["geometry"]
        props = row.drop("geometry").to_dict()
        feature = {
            "type": "Feature",
            "properties": props,
            "geometry": {
                "type": "Polygon",
                "coordinates": [list(poly.exterior.coords)]
            }
        }
        geojson_features.append(feature)

    geojson_data = {
        "type": "FeatureCollection",
        "name": "coimbatore_grid_1km",
        "crs": {"type": "name", "properties": {"name": "EPSG:32643"}},
        "features": geojson_features,
    }
    with open(geo_proc_dir / "grid_1km.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, indent=2)

    logger.info("Saved master geospatial feature datasets to %s", geo_proc_dir)

    # Run Quality Checks A through O
    validator = GridValidator(grid_df)
    qa_report = validator.validate()

    # Save QA Report JSON
    with open(meta_dir / "validation_phase2_geospatial.json", "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2)

    logger.info("Phase 2 Geospatial Build Complete! Quality Check Valid=%s", qa_report["is_valid"])


if __name__ == "__main__":
    main()
