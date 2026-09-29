"""
GramDrishti -- Water / Coastline Ingestion
============================================
Ingests water body and coastline vector datasets.

Validates:
  - CRS
  - geometry validity
  - feature count
  - spatial extent
  - missing geometries
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.ingestion.validation_utils import (
    ValidationReport,
    generate_metadata,
    get_project_root,
    load_config,
    save_metadata,
    save_report,
    validate_file_exists,
)

logger = logging.getLogger("gramdrishti.ingestion.water")


class WaterIngestor:
    """Ingestor for water body and coastline vector datasets."""

    def __init__(self, input_path: str | Path, config_path: str | Path | None = None):
        self.input_path = Path(input_path)
        self.config = load_config(config_path)
        self.source_config = self.config["data_sources"]["water"]
        self.project_root = get_project_root()
        self.processed_dir = self.project_root / self.source_config["processed_dir"]
        self.report = ValidationReport(
            dataset_name=self.source_config["dataset_name"],
            source_key="water",
        )
        self._gdf = None

    def run(self) -> ValidationReport:
        logger.info("Starting water/coast ingestion from %s", self.input_path)
        try:
            self._validate_file()
            self._load_data()
            self._validate_geometries()
            self._report_crs()
            self._report_spatial_extent()
            self._report_record_count()
            self._report_missing_values()
            self._save_processed()
        except Exception as exc:
            self.report.add_error(f"Fatal: {exc}")

        self.report.status = "READY" if self.report.is_valid else "PARTIAL"
        self.report.fields_present = ["geometry"]
        save_report(self.report)
        meta = generate_metadata("water", self.report, self.source_config,
                                 data_provenance="UNVERIFIED")
        meta["original_filename"] = self.input_path.name
        save_metadata(meta, "water")
        return self.report

    def _validate_file(self):
        ok, msg = validate_file_exists(self.input_path)
        if not ok:
            raise FileNotFoundError(msg)
        ext = self.input_path.suffix.lstrip(".").lower()
        self.report.file_format = ext

    def _load_data(self):
        import geopandas as gpd
        ext = self.input_path.suffix.lower()
        if ext in (".shp", ".geojson", ".gpkg"):
            self._gdf = gpd.read_file(self.input_path)
            self.report.record_count = len(self._gdf)
            logger.info("Loaded %d water features", len(self._gdf))
        else:
            raise ValueError(f"Unsupported water data format: {ext}")

    def _validate_geometries(self):
        if self._gdf is None:
            return
        invalid = int((~self._gdf.geometry.is_valid).sum())
        if invalid > 0:
            self.report.add_warning(f"{invalid} features have invalid geometries")
        empty = int(self._gdf.geometry.is_empty.sum())
        if empty > 0:
            self.report.add_warning(f"{empty} features have empty geometries")
        null = int(self._gdf.geometry.isna().sum())
        if null > 0:
            self.report.add_error(f"{null} features have null/missing geometries")

    def _report_crs(self):
        if self._gdf is not None and self._gdf.crs:
            self.report.crs_detected = str(self._gdf.crs)
        else:
            self.report.add_warning("No CRS detected")

    def _report_spatial_extent(self):
        if self._gdf is not None and not self._gdf.empty:
            bounds = self._gdf.total_bounds
            self.report.spatial_extent = {
                "min_lon": float(bounds[0]), "min_lat": float(bounds[1]),
                "max_lon": float(bounds[2]), "max_lat": float(bounds[3]),
            }

    def _report_record_count(self):
        if self._gdf is not None:
            self.report.record_count = len(self._gdf)

    def _report_missing_values(self):
        if self._gdf is None or self._gdf.empty:
            return
        total = len(self._gdf)
        for col in self._gdf.columns:
            n = int(self._gdf[col].isna().sum())
            if n > 0:
                self.report.missing_value_counts[col] = n
                self.report.missing_value_percentages[col] = round(n / total * 100, 2)

    def _save_processed(self):
        if self._gdf is None or self._gdf.empty:
            self.report.add_warning("No data to save")
            return
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        out = self.processed_dir / f"{self.input_path.stem}_processed.gpkg"
        self._gdf.to_file(out, driver="GPKG")
        logger.info("Processed water data saved: %s", out)
