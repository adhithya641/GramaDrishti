"""
GramDrishti -- DEM Ingestion
==============================
Ingests Digital Elevation Model raster data (GeoTIFF).

Validates:
  - CRS, resolution, bounds, width, height
  - nodata value, nodata percentage
  - min/max elevation
  - spatial coverage

Does NOT compute slope, aspect, or TRI (Phase 2).
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

logger = logging.getLogger("gramdrishti.ingestion.dem")


class DEMIngestor:
    """
    Ingestor for DEM raster datasets (GeoTIFF).

    Parameters
    ----------
    input_path : str | Path
        Path to the raw DEM raster file.
    config_path : str | Path | None
        Override path to data_sources.yaml.
    """

    def __init__(self, input_path: str | Path, config_path: str | Path | None = None):
        self.input_path = Path(input_path)
        self.config = load_config(config_path)
        self.source_config = self.config["data_sources"]["dem"]
        self.project_root = get_project_root()
        self.processed_dir = self.project_root / self.source_config["processed_dir"]
        self.report = ValidationReport(
            dataset_name=self.source_config["dataset_name"],
            source_key="dem",
        )
        self._raster = None
        self._array = None

    def run(self) -> ValidationReport:
        logger.info("Starting DEM ingestion from %s", self.input_path)
        try:
            self._validate_file()
            self._load_data()
            self._report_crs()
            self._report_resolution()
            self._report_bounds()
            self._report_dimensions()
            self._report_nodata()
            self._report_elevation_range()
            self._save_processed()
        except Exception as exc:
            self.report.add_error(f"Fatal: {exc}")
            logger.error("DEM ingestion failed: %s", exc, exc_info=True)

        self.report.status = "READY" if self.report.is_valid else "PARTIAL"
        self.report.fields_present = ["elevation"]
        save_report(self.report)
        meta = generate_metadata("dem", self.report, self.source_config,
                                 data_provenance="UNVERIFIED")
        meta["original_filename"] = self.input_path.name
        save_metadata(meta, "dem")
        logger.info("DEM ingestion complete. Valid=%s", self.report.is_valid)
        return self.report

    def _validate_file(self):
        ok, msg = validate_file_exists(self.input_path)
        if not ok:
            raise FileNotFoundError(msg)
        ext = self.input_path.suffix.lstrip(".").lower()
        self.report.file_format = ext
        expected = [f.lower() for f in self.source_config.get("format", [])]
        if ext not in expected:
            self.report.add_warning(f"Format '{ext}' not in expected {expected}")

    def _load_data(self):
        import rasterio
        self._raster = rasterio.open(self.input_path)
        self._array = self._raster.read(1)
        self.report.record_count = self._array.size
        logger.info("Loaded DEM: %dx%d (%d pixels)", self._raster.width, self._raster.height,
                     self._array.size)

    def _report_crs(self):
        if self._raster and self._raster.crs:
            self.report.crs_detected = str(self._raster.crs)
            logger.info("CRS: %s", self.report.crs_detected)
        else:
            self.report.add_warning("No CRS detected")

    def _report_resolution(self):
        if self._raster:
            res = self._raster.res
            self.report.resolution = f"{res[0]}x{res[1]}"
            logger.info("Resolution: %s", self.report.resolution)

    def _report_bounds(self):
        if self._raster:
            b = self._raster.bounds
            self.report.spatial_extent = {
                "min_lon": b.left,
                "min_lat": b.bottom,
                "max_lon": b.right,
                "max_lat": b.top,
            }
            logger.info("Bounds: %s", self.report.spatial_extent)

    def _report_dimensions(self):
        if self._raster:
            logger.info("Width: %d, Height: %d", self._raster.width, self._raster.height)

    def _report_nodata(self):
        if self._raster is None or self._array is None:
            return
        nodata = self._raster.nodata
        if nodata is not None:
            n_nodata = int(np.sum(self._array == nodata))
            total = self._array.size
            pct = round(n_nodata / total * 100, 2) if total > 0 else 0
            self.report.missing_value_counts["nodata"] = n_nodata
            self.report.missing_value_percentages["nodata"] = pct
            logger.info("Nodata value: %s, count: %d (%.2f%%)", nodata, n_nodata, pct)
        else:
            # Check for NaN if floating point
            if np.issubdtype(self._array.dtype, np.floating):
                n_nan = int(np.isnan(self._array).sum())
                if n_nan > 0:
                    total = self._array.size
                    self.report.missing_value_counts["nan"] = n_nan
                    self.report.missing_value_percentages["nan"] = round(
                        n_nan / total * 100, 2
                    )
            self.report.add_warning("No nodata value defined in raster metadata")

    def _report_elevation_range(self):
        if self._array is None:
            return
        nodata = self._raster.nodata if self._raster else None
        valid = self._array.copy().astype(float)
        if nodata is not None:
            valid[self._array == nodata] = np.nan
        valid_flat = valid[~np.isnan(valid)]
        if valid_flat.size > 0:
            elev_min = float(np.min(valid_flat))
            elev_max = float(np.max(valid_flat))
            logger.info("Elevation range: %.1f to %.1f m", elev_min, elev_max)
            self.report.add_limitation(f"Elevation min={elev_min}m, max={elev_max}m")
        else:
            self.report.add_warning("No valid elevation values found")

    def _save_processed(self):
        if self._raster is None:
            self.report.add_warning("No DEM data to save")
            return
        import rasterio
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        out = self.processed_dir / f"{self.input_path.stem}_processed.tif"
        profile = self._raster.profile.copy()
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(self._raster.read())
        logger.info("Processed DEM saved: %s", out)
