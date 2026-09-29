"""
GramDrishti -- Land Cover Ingestion
======================================
Ingests LULC raster or vector data.

Validates:
  - CRS, spatial extent, resolution
  - feature/pixel count
  - nodata information

Does NOT compute ML features (Phase 2).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from src.ingestion.validation_utils import (
    ValidationReport,
    generate_metadata,
    get_project_root,
    load_config,
    save_metadata,
    save_report,
    validate_file_exists,
)

logger = logging.getLogger("gramdrishti.ingestion.landcover")


class LandcoverIngestor:
    """
    Ingestor for LULC datasets (raster GeoTIFF or vector).
    """

    def __init__(self, input_path: str | Path, config_path: str | Path | None = None):
        self.input_path = Path(input_path)
        self.config = load_config(config_path)
        self.source_config = self.config["data_sources"]["landcover"]
        self.project_root = get_project_root()
        self.processed_dir = self.project_root / self.source_config["processed_dir"]
        self.report = ValidationReport(
            dataset_name=self.source_config["dataset_name"],
            source_key="landcover",
        )
        self._raster = None
        self._array = None
        self._gdf = None
        self._data_type: Optional[str] = None

    def run(self) -> ValidationReport:
        logger.info("Starting landcover ingestion from %s", self.input_path)
        try:
            self._validate_file()
            self._load_data()
            self._report_crs()
            self._report_spatial_extent()
            self._report_resolution()
            self._report_record_count()
            self._report_nodata()
            self._save_processed()
        except Exception as exc:
            self.report.add_error(f"Fatal: {exc}")

        self.report.status = "READY" if self.report.is_valid else "PARTIAL"
        self.report.fields_present = ["landcover_class"]
        save_report(self.report)
        meta = generate_metadata("landcover", self.report, self.source_config,
                                 data_provenance="UNVERIFIED")
        meta["original_filename"] = self.input_path.name
        save_metadata(meta, "landcover")
        return self.report

    def _validate_file(self):
        ok, msg = validate_file_exists(self.input_path)
        if not ok:
            raise FileNotFoundError(msg)
        ext = self.input_path.suffix.lstrip(".").lower()
        self.report.file_format = ext

    def _load_data(self):
        ext = self.input_path.suffix.lower()
        if ext in (".tif", ".tiff"):
            import rasterio
            self._raster = rasterio.open(self.input_path)
            self._array = self._raster.read(1)
            self._data_type = "raster"
            logger.info("Loaded landcover raster: %dx%d", self._raster.width, self._raster.height)
        elif ext in (".shp", ".geojson", ".gpkg"):
            import geopandas as gpd
            self._gdf = gpd.read_file(self.input_path)
            self._data_type = "vector"
            logger.info("Loaded landcover vector: %d features", len(self._gdf))
        else:
            raise ValueError(f"Unsupported format: {ext}")

    def _report_crs(self):
        if self._data_type == "raster" and self._raster and self._raster.crs:
            self.report.crs_detected = str(self._raster.crs)
        elif self._data_type == "vector" and self._gdf is not None and self._gdf.crs:
            self.report.crs_detected = str(self._gdf.crs)
        else:
            self.report.add_warning("No CRS detected")

    def _report_spatial_extent(self):
        if self._data_type == "raster" and self._raster:
            b = self._raster.bounds
            self.report.spatial_extent = {
                "min_lon": b.left, "min_lat": b.bottom,
                "max_lon": b.right, "max_lat": b.top,
            }
        elif self._data_type == "vector" and self._gdf is not None and not self._gdf.empty:
            bounds = self._gdf.total_bounds
            self.report.spatial_extent = {
                "min_lon": float(bounds[0]), "min_lat": float(bounds[1]),
                "max_lon": float(bounds[2]), "max_lat": float(bounds[3]),
            }

    def _report_resolution(self):
        if self._data_type == "raster" and self._raster:
            self.report.resolution = f"{self._raster.res[0]}x{self._raster.res[1]}"

    def _report_record_count(self):
        if self._data_type == "raster" and self._array is not None:
            self.report.record_count = self._array.size
            unique = len(np.unique(self._array))
            logger.info("Unique landcover classes: %d", unique)
        elif self._data_type == "vector" and self._gdf is not None:
            self.report.record_count = len(self._gdf)

    def _report_nodata(self):
        if self._data_type != "raster" or self._array is None:
            return
        nodata = self._raster.nodata if self._raster else None
        if nodata is not None:
            n = int(np.sum(self._array == nodata))
            total = self._array.size
            if n > 0:
                self.report.missing_value_counts["nodata"] = n
                self.report.missing_value_percentages["nodata"] = round(n / total * 100, 2)
        elif np.issubdtype(self._array.dtype, np.floating):
            n = int(np.isnan(self._array).sum())
            if n > 0:
                self.report.missing_value_counts["nan"] = n
                self.report.missing_value_percentages["nan"] = round(
                    n / self._array.size * 100, 2
                )

    def _save_processed(self):
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        if self._data_type == "raster" and self._raster:
            import rasterio
            out = self.processed_dir / f"{self.input_path.stem}_processed.tif"
            profile = self._raster.profile.copy()
            with rasterio.open(out, "w", **profile) as dst:
                dst.write(self._raster.read())
        elif self._data_type == "vector" and self._gdf is not None:
            out = self.processed_dir / f"{self.input_path.stem}_processed.gpkg"
            self._gdf.to_file(out, driver="GPKG")
        else:
            self.report.add_warning("No data to save")
            return
        logger.info("Processed landcover saved: %s", out)
