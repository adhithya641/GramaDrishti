"""
GramDrishti — Phase 2 Geospatial Unit Tests
============================================
Tests metric grid generation (EPSG:32643), spatial Panchayat assignment,
DEM/slope/aspect/TRI feature engineering, land cover class fractions,
water distance, forecast parent alignment, and Quality Checks A-O.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.geospatial.crs_grid import UTM32643Transformer, generate_1km_grid
from src.geospatial.panchayat_assignment import assign_panchayats
from src.geospatial.terrain_features import compute_terrain_features, _compute_dem_derivatives
from src.geospatial.landcover_features import compute_landcover_features
from src.geospatial.hydro_features import compute_hydro_features
from src.geospatial.forecast_alignment import align_forecast_grid
from src.geospatial.validate_grid import GridValidator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestCRSAndGrid:
    """Tests for projected metric grid generation in EPSG:32643."""

    def test_utm_transformer_roundtrip(self):
        transformer = UTM32643Transformer()
        orig_lon, orig_lat = 76.9600, 10.9900
        x, y = transformer.transform_to_utm(orig_lon, orig_lat)
        rev_lon, rev_lat = transformer.transform_to_wgs84(x, y)

        assert abs(orig_lon - rev_lon) < 1e-5
        assert abs(orig_lat - rev_lat) < 1e-5

    def test_grid_generation_structure(self):
        df = generate_1km_grid(min_lat=10.90, max_lat=11.10, min_lon=76.80, max_lon=77.00)
        assert not df.empty
        assert "grid_id" in df.columns
        assert "centroid_x" in df.columns
        assert "centroid_y" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert "geometry" in df.columns

    def test_grid_cell_spacing(self):
        df = generate_1km_grid(min_lat=10.90, max_lat=11.10, min_lon=76.80, max_lon=77.00)
        widths = df["max_x"] - df["min_x"]
        heights = df["max_y"] - df["min_y"]

        assert np.allclose(widths, 1000.0)
        assert np.allclose(heights, 1000.0)


class TestPanchayatAssignment:
    """Tests for spatial Panchayat assignment."""

    def test_panchayat_assignment(self):
        grid_df = generate_1km_grid(min_lat=10.95, max_lat=11.05, min_lon=76.90, max_lon=77.00)
        geojson_path = PROJECT_ROOT / "data" / "raw" / "boundaries" / "coimbatore_panchayats.geojson"

        assigned_df, diag = assign_panchayats(grid_df, geojson_path)

        assert "panchayat_id" in assigned_df.columns
        assert "panchayat_name" in assigned_df.columns
        assert "block_name" in assigned_df.columns
        assert "district_name" in assigned_df.columns
        assert assigned_df["panchayat_name"].isna().sum() == 0
        assert diag["total_cells"] == len(grid_df)


class TestTerrainDerivatives:
    """Tests for DEM elevation, slope, aspect, and TRI calculations."""

    def test_dem_derivatives_calculation(self):
        # Create a simple synthetic elevation gradient (3x3 pixels)
        dem = np.array([
            [100.0, 110.0, 120.0],
            [100.0, 110.0, 120.0],
            [100.0, 110.0, 120.0],
        ], dtype=np.float32)

        slope_deg, aspect_deg, tri = _compute_dem_derivatives(dem, cell_res_m=30.0)

        assert slope_deg.shape == (3, 3)
        assert aspect_deg.shape == (3, 3)
        assert tri.shape == (3, 3)
        assert (slope_deg >= 0.0).all()
        assert (tri >= 0.0).all()

    def test_terrain_features_computation(self):
        grid_df = generate_1km_grid(min_lat=10.95, max_lat=11.05, min_lon=76.90, max_lon=77.00)
        dem_path = PROJECT_ROOT / "data" / "raw" / "dem" / "coimbatore_dem_30m.tif"

        df_out = compute_terrain_features(grid_df, dem_path)

        for col in ["elevation_mean", "elevation_std", "slope_mean", "aspect_sin", "aspect_cos", "tri_mean"]:
            assert col in df_out.columns
            assert df_out[col].isna().sum() == 0

        # Trigonometric sin/cos bound check
        assert (df_out["aspect_sin"].abs() <= 1.0001).all()
        assert (df_out["aspect_cos"].abs() <= 1.0001).all()


class TestLandcoverFeatures:
    """Tests for LULC class fractions."""

    def test_landcover_features_computation(self):
        grid_df = generate_1km_grid(min_lat=10.95, max_lat=11.05, min_lon=76.90, max_lon=77.00)
        lc_path = PROJECT_ROOT / "data" / "raw" / "landcover" / "coimbatore_landcover_10m.tif"

        df_out = compute_landcover_features(grid_df, lc_path)

        assert "dominant_landcover_class" in df_out.columns
        assert "landcover_fraction_cropland" in df_out.columns

        # Sum of fractions should equal ~1.0
        frac_sum = (
            df_out["landcover_fraction_tree"]
            + df_out["landcover_fraction_shrub"]
            + df_out["landcover_fraction_grass"]
            + df_out["landcover_fraction_cropland"]
            + df_out["landcover_fraction_builtup"]
            + df_out["landcover_fraction_water"]
            + df_out["nodata_fraction"]
        )

        assert np.allclose(frac_sum, 1.0, atol=0.01)


class TestHydroFeatures:
    """Tests for distance to water calculations."""

    def test_hydro_distance_computation(self):
        grid_df = generate_1km_grid(min_lat=10.95, max_lat=11.05, min_lon=76.90, max_lon=77.00)
        water_path = PROJECT_ROOT / "data" / "raw" / "water" / "coimbatore_water_bodies.geojson"

        df_out = compute_hydro_features(grid_df, water_path)

        assert "distance_to_nearest_water" in df_out.columns
        assert (df_out["distance_to_nearest_water"] >= 0.0).all()


class TestForecastAlignment:
    """Tests for forecast parent grid mapping."""

    def test_forecast_alignment(self):
        grid_df = generate_1km_grid(min_lat=10.95, max_lat=11.05, min_lon=76.90, max_lon=77.00)
        fc_path = PROJECT_ROOT / "data" / "raw" / "forecasts" / "coimbatore_historical_forecasts.csv"

        df_out, fc_parents_df, diag = align_forecast_grid(grid_df, fc_path)

        assert "forecast_parent_id" in df_out.columns
        assert df_out["forecast_parent_id"].isna().sum() == 0
        assert not fc_parents_df.empty
        assert diag["total_cells_mapped"] == len(grid_df)


class TestMasterGridValidator:
    """Tests for GridValidator quality checks A through O."""

    def test_grid_validator_on_master_data(self):
        master_csv = PROJECT_ROOT / "data" / "processed" / "geospatial" / "geospatial_features_master.csv"
        assert master_csv.exists()

        df = pd.read_csv(master_csv)
        df["geometry"] = [1] * len(df)  # Placeholder non-null geometry for validation

        validator = GridValidator(df)
        report = validator.validate()

        assert report["is_valid"] is True
        assert len(report["issues"]) == 0
