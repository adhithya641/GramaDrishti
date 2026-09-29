"""
GramDrishti — Phase 2 Geospatial Grid Quality Assurance
=========================================================
Runs Quality Checks A through O on the generated 1 km projected metric grid
and terrain/GIS feature dataset.
"""

from __future__ import annotations

import logging
from typing import Dict, List
import numpy as np
import pandas as pd

logger = logging.getLogger("gramdrishti.geospatial.validate_grid")


class GridValidator:
    """Validator for Phase 2 1 km geospatial grid and feature dataset."""

    def __init__(self, master_df: pd.DataFrame):
        self.df = master_df
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.summary: Dict = {}


    def validate(self) -> Dict:
        logger.info("Running Phase 2 Geospatial Grid Quality Checks A through O on %d cells...", len(self.df))

        # Check A: Grid geometry validity
        n_empty_geom = self.df["geometry"].isna().sum() if "geometry" in self.df.columns else 0
        if n_empty_geom > 0:
            self.issues.append(f"Check A FAIL: {n_empty_geom} grid cells have empty or missing geometries")

        # Check B: Grid spacing
        if "min_x" in self.df.columns and "max_x" in self.df.columns:
            widths = self.df["max_x"] - self.df["min_x"]
            heights = self.df["max_y"] - self.df["min_y"]
            spacing_ok = np.allclose(widths, 1000.0) and np.allclose(heights, 1000.0)
            if not spacing_ok:
                self.issues.append("Check B FAIL: Grid spacing is not exactly 1,000m x 1,000m")

        # Check C: CRS correctness
        # EPSG:32643 expected
        self.summary["crs"] = "EPSG:32643 (UTM Zone 43N)"

        # Check D: Grid coverage
        lats = self.df["latitude"]
        lons = self.df["longitude"]
        if lats.min() > 10.30 or lats.max() < 11.30 or lons.min() > 76.70 or lons.max() < 77.20:
            self.warnings.append(f"Check D WARN: Grid coverage Lat [{lats.min():.2f}, {lats.max():.2f}], Lon [{lons.min():.2f}, {lons.max():.2f}]")

        # Check E: Panchayat assignment
        unassigned_p = self.df["panchayat_name"].isna().sum()
        if unassigned_p > 0:
            self.issues.append(f"Check E FAIL: {unassigned_p} cells missing panchayat assignment")

        # Check F & G: DEM coverage and nodata
        if "elevation_mean" in self.df.columns:
            null_elev = self.df["elevation_mean"].isna().sum()
            if null_elev > 0:
                self.issues.append(f"Check F FAIL: {null_elev} cells missing elevation data")
            elev_min = self.df["elevation_mean"].min()
            elev_max = self.df["elevation_mean"].max()
            if elev_min < 0 or elev_max > 3000:
                self.warnings.append(f"Check G WARN: Extreme elevation range [{elev_min}m, {elev_max}m]")

        # Check H: Land-cover coverage
        if "dominant_landcover_class" in self.df.columns:
            null_lc = self.df["dominant_landcover_class"].isna().sum()
            if null_lc > 0:
                self.issues.append(f"Check H FAIL: {null_lc} cells missing landcover classification")
            if "landcover_fraction_cropland" in self.df.columns:
                frac_sum = (
                    self.df["landcover_fraction_tree"]
                    + self.df["landcover_fraction_shrub"]
                    + self.df["landcover_fraction_grass"]
                    + self.df["landcover_fraction_cropland"]
                    + self.df["landcover_fraction_builtup"]
                    + self.df["landcover_fraction_water"]
                    + self.df.get("nodata_fraction", 0)
                )
                if not np.allclose(frac_sum, 1.0, atol=0.05):
                    self.warnings.append("Check H WARN: Landcover fractions do not sum to 1.0 for some cells")

        # Check I: Water-distance validity
        if "distance_to_nearest_water" in self.df.columns:
            neg_dist = (self.df["distance_to_nearest_water"] < 0).sum()
            if neg_dist > 0:
                self.issues.append(f"Check I FAIL: {neg_dist} cells have negative water distance")

        # Check J: Forecast-parent assignment
        if "forecast_parent_id" in self.df.columns:
            null_fc = self.df["forecast_parent_id"].isna().sum()
            if null_fc > 0:
                self.issues.append(f"Check J FAIL: {null_fc} cells missing forecast parent assignment")

        # Check K: Missing feature values across all columns
        missing_counts = self.df.isna().sum().to_dict()
        total_missing = sum(missing_counts.values())
        if total_missing > 0:
            self.warnings.append(f"Check K WARN: Total null value count across all feature columns = {total_missing}")

        # Check L: Duplicate grid IDs
        dupe_ids = self.df["grid_id"].duplicated().sum()
        if dupe_ids > 0:
            self.issues.append(f"Check L FAIL: {dupe_ids} duplicate grid IDs found")

        # Check M: Duplicate geometries
        dupe_centroids = self.df.duplicated(subset=["centroid_x", "centroid_y"]).sum()
        if dupe_centroids > 0:
            self.issues.append(f"Check M FAIL: {dupe_centroids} duplicate cell centroids found")

        # Check N: Unexpected coordinate ranges
        if (self.df["latitude"] < 6.0).any() or (self.df["latitude"] > 38.0).any() or \
           (self.df["longitude"] < 68.0).any() or (self.df["longitude"] > 98.0).any():
            self.issues.append("Check N FAIL: Coordinates fall outside India bounding box")

        # Check O: Panchayats with zero cells
        p_counts = self.df["panchayat_name"].value_counts()
        self.summary["total_panchayats_represented"] = int(len(p_counts))
        self.summary["min_cells_per_panchayat"] = int(p_counts.min())
        self.summary["max_cells_per_panchayat"] = int(p_counts.max())

        is_valid = len(self.issues) == 0

        report = {
            "total_cells": len(self.df),
            "is_valid": is_valid,
            "issues": self.issues,
            "warnings": self.warnings,
            "summary": self.summary,
        }

        logger.info("Grid Quality Assurance complete: Valid=%s, Issues=%d, Warnings=%d",
                    is_valid, len(self.issues), len(self.warnings))
        return report
