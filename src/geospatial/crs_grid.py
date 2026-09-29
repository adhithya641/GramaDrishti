"""
GramDrishti — Projected Metric Grid Generator
==============================================
Generates a regular ~1 km x 1 km projected metric grid in EPSG:32643 (UTM Zone 43N)
covering the pilot region (Coimbatore District, Tamil Nadu).

Coordinates:
  - Projected CRS: EPSG:32643 (UTM Zone 43N, WGS 84, meters)
  - Geographic CRS: EPSG:4326 (WGS 84, degrees)

Grid cell properties:
  - grid_id
  - centroid_x (meters, EPSG:32643)
  - centroid_y (meters, EPSG:32643)
  - latitude (degrees, EPSG:4326)
  - longitude (degrees, EPSG:4326)
  - geometry (Shapely Polygon in EPSG:32643)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

logger = logging.getLogger("gramdrishti.geospatial.crs_grid")

TARGET_CRS_EPSG = 32643
TARGET_CRS_NAME = "EPSG:32643 (UTM Zone 43N)"
GRID_CELL_SIZE_M = 1000.0  # 1 km x 1 km


class UTM32643Transformer:
    """
    Pure Python / NumPy WGS84 (EPSG:4326) <-> UTM Zone 43N (EPSG:32643) coordinate transformer.
    Ensures zero C-extension DLL dependency for Windows compatibility.
    """

    def __init__(self):
        self.a = 6378137.0  # WGS84 semi-major axis
        self.f = 1.0 / 298.257223563  # WGS84 flattening
        self.e2 = 2.0 * self.f - self.f ** 2
        self.e_prime2 = self.e2 / (1.0 - self.e2)
        self.k0 = 0.9996  # UTM scale factor
        self.lon0 = np.radians(75.0)  # Central meridian for Zone 43N (75° E)
        self.false_e = 500000.0
        self.false_n = 0.0

    def transform_to_utm(self, lon: float, lat: float) -> Tuple[float, float]:
        """Convert WGS84 (lon, lat) degrees to UTM Zone 43N (X, Y) meters."""
        lon_rad = np.radians(lon)
        lat_rad = np.radians(lat)

        N = self.a / np.sqrt(1.0 - self.e2 * np.sin(lat_rad) ** 2)
        T = np.tan(lat_rad) ** 2
        C = self.e_prime2 * np.cos(lat_rad) ** 2
        A = (lon_rad - self.lon0) * np.cos(lat_rad)

        M = self.a * (
            (1.0 - self.e2 / 4.0 - 3.0 * self.e2 ** 2 / 64.0 - 5.0 * self.e2 ** 3 / 256.0) * lat_rad
            - (3.0 * self.e2 / 8.0 + 3.0 * self.e2 ** 2 / 32.0 + 45.0 * self.e2 ** 3 / 1024.0) * np.sin(2.0 * lat_rad)
            + (15.0 * self.e2 ** 2 / 256.0 + 45.0 * self.e2 ** 3 / 1024.0) * np.sin(4.0 * lat_rad)
            - (35.0 * self.e2 ** 3 / 3072.0) * np.sin(6.0 * lat_rad)
        )

        x = self.false_e + self.k0 * N * (
            A + (1.0 - T + C) * A ** 3 / 6.0
            + (5.0 - 18.0 * T + T ** 2 + 72.0 * C - 58.0 * self.e_prime2) * A ** 5 / 120.0
        )
        y = self.false_n + self.k0 * (
            M + N * np.tan(lat_rad) * (
                A ** 2 / 2.0
                + (5.0 - T + 9.0 * C + 4.0 * C ** 2) * A ** 4 / 24.0
                + (61.0 - 58.0 * T + T ** 2 + 600.0 * C - 330.0 * self.e_prime2) * A ** 6 / 720.0
            )
        )
        return float(x), float(y)

    def transform_to_wgs84(self, x: float, y: float) -> Tuple[float, float]:
        """Convert UTM Zone 43N (X, Y) meters to WGS84 (lon, lat) degrees."""
        x_adj = x - self.false_e
        y_adj = y - self.false_n
        M = y_adj / self.k0

        mu = M / (self.a * (1.0 - self.e2 / 4.0 - 3.0 * self.e2 ** 2 / 64.0 - 5.0 * self.e2 ** 3 / 256.0))
        e1 = (1.0 - np.sqrt(1.0 - self.e2)) / (1.0 + np.sqrt(1.0 - self.e2))

        phi1 = (
            mu + (3.0 * e1 / 2.0 - 27.0 * e1 ** 3 / 32.0) * np.sin(2.0 * mu)
            + (21.0 * e1 ** 2 / 16.0 - 55.0 * e1 ** 4 / 32.0) * np.sin(4.0 * mu)
            + (151.0 * e1 ** 3 / 96.0) * np.sin(6.0 * mu)
        )

        N1 = self.a / np.sqrt(1.0 - self.e2 * np.sin(phi1) ** 2)
        T1 = np.tan(phi1) ** 2
        C1 = self.e_prime2 * np.cos(phi1) ** 2
        R1 = self.a * (1.0 - self.e2) / (1.0 - self.e2 * np.sin(phi1) ** 2) ** 1.5
        D = x_adj / (N1 * self.k0)

        lat = phi1 - (N1 * np.tan(phi1) / R1) * (
            D ** 2 / 2.0
            - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 ** 2 - 9.0 * self.e_prime2) * D ** 4 / 24.0
            + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 ** 2 - 252.0 * self.e_prime2) * D ** 6 / 720.0
        )
        lon = self.lon0 + (
            D - (1.0 + 2.0 * T1 + C1) * D ** 3 / 6.0
            + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 ** 2 + 8.0 * self.e_prime2 + 24.0 * T1 ** 2) * D ** 5 / 120.0
        ) / np.cos(phi1)

        return float(np.degrees(lon)), float(np.degrees(lat))


def generate_1km_grid(
    min_lat: float = 10.20,
    max_lat: float = 11.40,
    min_lon: float = 76.60,
    max_lon: float = 77.30,
) -> pd.DataFrame:
    """
    Generate a regular 1 km x 1 km metric grid in EPSG:32643 covering the bounding box.

    Parameters
    ----------
    min_lat, max_lat, min_lon, max_lon : float
        Geographic bounding box in WGS84 degrees.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: grid_id, centroid_x, centroid_y, latitude, longitude,
        min_x, min_y, max_x, max_y, geometry
    """
    transformer = UTM32643Transformer()

    # Transform 4 bounding box corners to projected UTM meters
    x1, y1 = transformer.transform_to_utm(min_lon, min_lat)
    x2, y2 = transformer.transform_to_utm(max_lon, min_lat)
    x3, y3 = transformer.transform_to_utm(min_lon, max_lat)
    x4, y4 = transformer.transform_to_utm(max_lon, max_lat)

    min_x = np.floor(min(x1, x2, x3, x4) / GRID_CELL_SIZE_M) * GRID_CELL_SIZE_M
    max_x = np.ceil(max(x1, x2, x3, x4) / GRID_CELL_SIZE_M) * GRID_CELL_SIZE_M
    min_y = np.floor(min(y1, y2, y3, y4) / GRID_CELL_SIZE_M) * GRID_CELL_SIZE_M
    max_y = np.ceil(max(y1, y2, y3, y4) / GRID_CELL_SIZE_M) * GRID_CELL_SIZE_M

    x_coords = np.arange(min_x, max_x, GRID_CELL_SIZE_M)
    y_coords = np.arange(min_y, max_y, GRID_CELL_SIZE_M)

    logger.info(
        "Generating metric 1 km grid (EPSG:32643): X=[%.1f, %.1f] (%d cols), Y=[%.1f, %.1f] (%d rows)",
        min_x, max_x, len(x_coords), min_y, max_y, len(y_coords),
    )

    records = []
    cell_idx = 1

    for y in y_coords:
        for x in x_coords:
            cx = x + GRID_CELL_SIZE_M / 2.0
            cy = y + GRID_CELL_SIZE_M / 2.0
            lon, lat = transformer.transform_to_wgs84(cx, cy)

            # Filter to ensure centroid falls within geographic pilot bounding box plus small padding
            if (min_lat - 0.02) <= lat <= (max_lat + 0.02) and (min_lon - 0.02) <= lon <= (max_lon + 0.02):
                grid_id = f"GRID_CBE_{cell_idx:05d}"
                poly = Polygon([
                    (x, y),
                    (x + GRID_CELL_SIZE_M, y),
                    (x + GRID_CELL_SIZE_M, y + GRID_CELL_SIZE_M),
                    (x, y + GRID_CELL_SIZE_M),
                    (x, y)
                ])

                records.append({
                    "grid_id": grid_id,
                    "centroid_x": round(float(cx), 2),
                    "centroid_y": round(float(cy), 2),
                    "latitude": round(float(lat), 6),
                    "longitude": round(float(lon), 6),
                    "min_x": round(float(x), 2),
                    "min_y": round(float(y), 2),
                    "max_x": round(float(x + GRID_CELL_SIZE_M), 2),
                    "max_y": round(float(y + GRID_CELL_SIZE_M), 2),
                    "geometry": poly,
                })
                cell_idx += 1

    df = pd.DataFrame(records)
    logger.info("Generated %d valid 1 km grid cells for Coimbatore pilot region", len(df))
    return df
