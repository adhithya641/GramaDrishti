"""
GramDrishti -- Panchayat Boundary Ingestion
=============================================
Ingests panchayat-level administrative boundary vector data.

Supported formats: GeoJSON, Shapefile, GeoPackage

Validates:
  - file existence
  - geometry validity
  - duplicate panchayat IDs
  - missing panchayat names
  - administrative hierarchy (state > district > block > panchayat)
  - CRS
  - spatial extent
  - feature count

Reports:
  - number of panchayats / blocks / districts
  - invalid geometries
  - duplicate IDs
  - missing attributes
  - CRS
  - bounding box

Saves cleaned data to data/processed/boundaries/.
Never overwrites data/raw/boundaries/.
Does NOT create a 1 km grid (Phase 2).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.ingestion.validation_utils import (
    ValidationReport,
    check_required_fields,
    find_column,
    generate_metadata,
    get_project_root,
    load_config,
    save_metadata,
    save_report,
    validate_file_exists,
)

logger = logging.getLogger("gramdrishti.ingestion.boundaries")


class BoundaryIngestor:
    """
    Ingestor for panchayat boundary polygon datasets.

    Parameters
    ----------
    input_path : str | Path
        Path to the raw boundary file (shp, geojson, gpkg).
    config_path : str | Path | None
        Override path to data_sources.yaml.
    """

    def __init__(self, input_path: str | Path, config_path: str | Path | None = None):
        self.input_path = Path(input_path)
        self.config = load_config(config_path)
        self.source_config = self.config["data_sources"]["boundaries"]
        self.project_root = get_project_root()
        self.processed_dir = self.project_root / self.source_config["processed_dir"]
        self.report = ValidationReport(
            dataset_name=self.source_config["dataset_name"],
            source_key="boundaries",
        )
        self._gdf = None

    def run(self) -> ValidationReport:
        """Execute the full ingestion pipeline."""
        logger.info("Starting boundary ingestion from %s", self.input_path)
        try:
            self._validate_file()
            self._load_data()
            self._validate_fields()
            self._validate_geometries()
            self._check_duplicate_ids()
            self._check_missing_names()
            self._report_hierarchy()
            self._report_crs()
            self._report_spatial_extent()
            self._report_missing_values()
            self._save_processed()
        except Exception as exc:
            self.report.add_error(f"Fatal: {exc}")
            logger.error("Boundary ingestion failed: %s", exc, exc_info=True)

        self.report.status = "READY" if self.report.is_valid else "PARTIAL"
        save_report(self.report)
        meta = generate_metadata("boundaries", self.report, self.source_config,
                                 data_provenance="UNVERIFIED")
        meta["original_filename"] = self.input_path.name
        save_metadata(meta, "boundaries")
        logger.info("Boundary ingestion complete. Valid=%s", self.report.is_valid)
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
        import geopandas as gpd
        self._gdf = gpd.read_file(self.input_path)
        self.report.record_count = len(self._gdf)
        logger.info("Loaded %d features from %s", len(self._gdf), self.input_path.name)

    def _validate_fields(self):
        if self._gdf is None:
            return
        columns = list(self._gdf.columns)
        if self._gdf.geometry is not None:
            columns.append("geometry")
        required = self.source_config.get("required_fields", [])
        present, missing = check_required_fields(columns, required)
        self.report.fields_present = present
        self.report.fields_missing = missing
        if missing:
            self.report.add_error(f"Missing required fields: {missing}")

    def _validate_geometries(self):
        if self._gdf is None:
            return
        invalid_count = int((~self._gdf.geometry.is_valid).sum())
        if invalid_count > 0:
            self.report.add_warning(f"{invalid_count} features have invalid geometries")
        empty_count = int(self._gdf.geometry.is_empty.sum())
        if empty_count > 0:
            self.report.add_warning(f"{empty_count} features have empty geometries")
        null_count = int(self._gdf.geometry.isna().sum())
        if null_count > 0:
            self.report.add_error(f"{null_count} features have null geometries")

    def _check_duplicate_ids(self):
        if self._gdf is None:
            return
        id_col = find_column(self._gdf, "panchayat_code")
        if id_col is None:
            id_col = find_column(self._gdf, "panchayat_name")
        if id_col is None:
            self.report.add_warning("No panchayat ID or name column found for duplicate check")
            return
        dupes = int(self._gdf[id_col].duplicated().sum())
        if dupes > 0:
            self.report.add_warning(f"{dupes} duplicate panchayat IDs/names in column '{id_col}'")
        else:
            logger.info("No duplicate panchayat IDs in '%s'", id_col)

    def _check_missing_names(self):
        if self._gdf is None:
            return
        name_col = find_column(self._gdf, "panchayat_name")
        if name_col is None:
            self.report.add_warning("No panchayat_name column for name check")
            return
        missing = int(self._gdf[name_col].isna().sum())
        if missing > 0:
            self.report.add_warning(f"{missing} features missing panchayat_name")

    def _report_hierarchy(self):
        """Report counts at each administrative level."""
        if self._gdf is None:
            return
        stats = {}
        for level in ["state_name", "district_name", "block_name", "panchayat_name"]:
            col = find_column(self._gdf, level)
            if col:
                stats[level] = int(self._gdf[col].nunique())
        if stats:
            logger.info("Administrative hierarchy: %s", stats)
            for level, count in stats.items():
                self.report.add_limitation(f"{level}: {count} unique values")

    def _report_crs(self):
        if self._gdf is not None and self._gdf.crs is not None:
            self.report.crs_detected = str(self._gdf.crs)
            logger.info("CRS: %s", self.report.crs_detected)
        else:
            self.report.add_warning("No CRS detected in boundary data")

    def _report_spatial_extent(self):
        if self._gdf is not None and not self._gdf.empty:
            bounds = self._gdf.total_bounds  # (minx, miny, maxx, maxy)
            self.report.spatial_extent = {
                "min_lon": float(bounds[0]),
                "min_lat": float(bounds[1]),
                "max_lon": float(bounds[2]),
                "max_lat": float(bounds[3]),
            }
            logger.info("Spatial extent: %s", self.report.spatial_extent)

    def _report_missing_values(self):
        if self._gdf is None or self._gdf.empty:
            return
        total = len(self._gdf)
        for col in self._gdf.columns:
            n_miss = int(self._gdf[col].isna().sum())
            if n_miss > 0:
                self.report.missing_value_counts[col] = n_miss
                self.report.missing_value_percentages[col] = round(
                    n_miss / total * 100, 2
                )

    def _save_processed(self):
        if self._gdf is None or self._gdf.empty:
            self.report.add_warning("No data to save")
            return
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.processed_dir / f"{self.input_path.stem}_processed.gpkg"
        self._gdf.to_file(out_path, driver="GPKG")
        logger.info("Processed boundaries saved: %s", out_path)
