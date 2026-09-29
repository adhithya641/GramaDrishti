"""
GramDrishti -- Weather Station Observation Ingestion
======================================================
Ingests ground weather station observation data (CSV).

Column mapping is configurable via configs/data_sources.yaml.

QC classification:
  VALID      - present and passes range/consistency checks
  MISSING    - null / NaN / absent
  SUSPICIOUS - present but outside expected range
  INVALID    - fails type or hard-limit checks

Does NOT:
  - automatically delete suspicious observations
  - interpolate missing observations
  - fabricate missing observations
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.ingestion.validation_utils import (
    ValidationReport,
    apply_column_mapping,
    check_required_fields,
    compute_missing_stats,
    find_column,
    generate_metadata,
    get_project_root,
    load_config,
    save_metadata,
    save_report,
    validate_coordinates_india,
    validate_file_exists,
)

logger = logging.getLogger("gramdrishti.ingestion.observations")

# Physical range limits for QC (hard limits -- INVALID if exceeded)
HARD_LIMITS = {
    "temperature": (-60.0, 60.0),
    "humidity": (0.0, 100.0),
    "rainfall": (0.0, 1000.0),
    "pressure": (870.0, 1085.0),
    "wind_speed": (0.0, 200.0),
}

# Soft limits for QC (suspicious if exceeded)
SOFT_LIMITS = {
    "temperature": (-10.0, 52.0),
    "humidity": (5.0, 100.0),
    "rainfall": (0.0, 500.0),
    "pressure": (940.0, 1060.0),
    "wind_speed": (0.0, 100.0),
}


class ObservationIngestor:
    """
    Ingestor for tabular weather station observation datasets.

    Parameters
    ----------
    input_path : str | Path
        Path to the raw CSV file.
    config_path : str | Path | None
        Override path to data_sources.yaml.
    """

    def __init__(self, input_path: str | Path, config_path: str | Path | None = None):
        self.input_path = Path(input_path)
        self.config = load_config(config_path)
        self.source_config = self.config["data_sources"]["observations"]
        self.project_root = get_project_root()
        self.processed_dir = self.project_root / self.source_config["processed_dir"]
        self.report = ValidationReport(
            dataset_name=self.source_config["dataset_name"],
            source_key="observations",
        )
        self._df: Optional[pd.DataFrame] = None
        self._qc: Optional[pd.DataFrame] = None

    def run(self) -> ValidationReport:
        """Execute the full ingestion and QC pipeline."""
        logger.info("Starting observation ingestion from %s", self.input_path)
        try:
            self._validate_file()
            self._load_data()
            self._apply_mapping()
            self._validate_fields()
            self._validate_station_ids()
            self._validate_timestamps()
            self._validate_coordinates()
            self._check_duplicate_records()
            self._report_missing_values()
            self._run_qc_classification()
            self._report_temporal_extent()
            self._report_spatial_extent()
            self._save_processed()
            self._save_qc_report()
        except Exception as exc:
            self.report.add_error(f"Fatal: {exc}")
            logger.error("Observation ingestion failed: %s", exc, exc_info=True)

        self.report.status = "READY" if self.report.is_valid else "PARTIAL"
        save_report(self.report)
        meta = generate_metadata("observations", self.report, self.source_config,
                                 data_provenance="UNVERIFIED")
        meta["original_filename"] = self.input_path.name
        save_metadata(meta, "observations")
        logger.info("Observation ingestion complete. Valid=%s", self.report.is_valid)
        return self.report

    # ---- Pipeline steps ---------------------------------------------------

    def _validate_file(self):
        ok, msg = validate_file_exists(self.input_path)
        if not ok:
            raise FileNotFoundError(msg)
        ext = self.input_path.suffix.lstrip(".").lower()
        self.report.file_format = ext
        if ext != "csv":
            self.report.add_warning(f"Expected CSV, got '{ext}'")

    def _load_data(self):
        self._df = pd.read_csv(self.input_path)
        self.report.record_count = len(self._df)
        logger.info("Loaded %d records from %s", len(self._df), self.input_path.name)

    def _apply_mapping(self):
        if self._df is None:
            return
        mapping = self.source_config.get("column_mapping", {})
        if mapping:
            self._df = apply_column_mapping(self._df, mapping)

    def _validate_fields(self):
        if self._df is None:
            return
        required = self.source_config.get("required_fields", [])
        present, missing = check_required_fields(list(self._df.columns), required)
        self.report.fields_present = present
        self.report.fields_missing = missing
        if missing:
            self.report.add_error(f"Missing required fields: {missing}")
        # Report optional fields
        optional = self.source_config.get("optional_fields", [])
        opt_present, opt_missing = check_required_fields(list(self._df.columns), optional)
        if opt_present:
            self.report.fields_present.extend(opt_present)

    def _validate_station_ids(self):
        if self._df is None:
            return
        col = find_column(self._df, "station_id")
        if col is None:
            return
        n_null = int(self._df[col].isna().sum())
        if n_null > 0:
            self.report.add_warning(f"{n_null} records have null station_id")
        n_unique = int(self._df[col].nunique())
        logger.info("Unique stations: %d", n_unique)

    def _validate_timestamps(self):
        if self._df is None:
            return
        col = find_column(self._df, "timestamp")
        if col is None:
            col = find_column(self._df, "date")
        if col is None:
            return
        parsed = pd.to_datetime(self._df[col], errors="coerce")
        n_unparseable = int(parsed.isna().sum() - self._df[col].isna().sum())
        if n_unparseable > 0:
            self.report.add_warning(f"{n_unparseable} records have unparseable timestamps")

    def _validate_coordinates(self):
        if self._df is None:
            return
        lat_col = find_column(self._df, "latitude")
        lon_col = find_column(self._df, "longitude")
        if lat_col is None or lon_col is None:
            return
        # Check for nulls
        lat_null = int(self._df[lat_col].isna().sum())
        lon_null = int(self._df[lon_col].isna().sum())
        if lat_null > 0:
            self.report.add_warning(f"{lat_null} records have null latitude")
        if lon_null > 0:
            self.report.add_warning(f"{lon_null} records have null longitude")
        # Check for invalid numeric
        lat_num = pd.to_numeric(self._df[lat_col], errors="coerce")
        lon_num = pd.to_numeric(self._df[lon_col], errors="coerce")
        lat_invalid = int(lat_num.isna().sum() - self._df[lat_col].isna().sum())
        lon_invalid = int(lon_num.isna().sum() - self._df[lon_col].isna().sum())
        if lat_invalid > 0:
            self.report.add_warning(f"{lat_invalid} records have non-numeric latitude")
        if lon_invalid > 0:
            self.report.add_warning(f"{lon_invalid} records have non-numeric longitude")
        # India bounds check
        valid_lats = lat_num.dropna()
        valid_lons = lon_num.dropna()
        if not valid_lats.empty and not valid_lons.empty:
            coord_warnings = validate_coordinates_india(
                float(valid_lats.min()), float(valid_lats.max()),
                float(valid_lons.min()), float(valid_lons.max()),
                self.config,
            )
            for w in coord_warnings:
                self.report.add_warning(w)

    def _check_duplicate_records(self):
        if self._df is None:
            return
        station_col = find_column(self._df, "station_id")
        ts_col = find_column(self._df, "timestamp") or find_column(self._df, "date")
        if station_col and ts_col:
            dupes = int(self._df.duplicated(subset=[station_col, ts_col]).sum())
            if dupes > 0:
                self.report.add_warning(
                    f"{dupes} duplicate station/timestamp records found"
                )
            else:
                logger.info("No duplicate station/timestamp records")

    def _report_missing_values(self):
        if self._df is None or self._df.empty:
            return
        total = len(self._df)
        raw_missing = {}
        for col in self._df.columns:
            n = int(self._df[col].isna().sum())
            if n > 0:
                raw_missing[col] = n
        counts, pcts = compute_missing_stats(raw_missing, total)
        self.report.missing_value_counts = counts
        self.report.missing_value_percentages = pcts
        # Threshold checks
        max_warn = self.config.get("validation", {}).get("max_missing_pct_warn", 10)
        max_fail = self.config.get("validation", {}).get("max_missing_pct_fail", 50)
        for col, pct in pcts.items():
            if pct >= max_fail:
                self.report.add_error(
                    f"Column '{col}' has {pct}% missing (threshold: {max_fail}%)"
                )
            elif pct >= max_warn:
                self.report.add_warning(
                    f"Column '{col}' has {pct}% missing (threshold: {max_warn}%)"
                )

    def _run_qc_classification(self):
        """
        Classify each value in weather variable columns as:
          VALID / MISSING / SUSPICIOUS / INVALID

        Does NOT delete or interpolate anything.
        """
        if self._df is None or self._df.empty:
            return
        weather_vars = ["temperature", "humidity", "rainfall", "pressure", "wind_speed"]
        qc_cols = {}
        for var in weather_vars:
            col = find_column(self._df, var)
            if col is None:
                continue
            series = pd.to_numeric(self._df[col], errors="coerce")
            qc = pd.Series("VALID", index=self._df.index)

            # MISSING
            qc[self._df[col].isna()] = "MISSING"

            # INVALID (non-numeric original that isn't null)
            non_numeric_mask = series.isna() & self._df[col].notna()
            qc[non_numeric_mask] = "INVALID"

            # Hard limits
            hard = HARD_LIMITS.get(var)
            if hard:
                below = series < hard[0]
                above = series > hard[1]
                qc[below & series.notna()] = "INVALID"
                qc[above & series.notna()] = "INVALID"

            # Soft limits (only for values not already INVALID)
            soft = SOFT_LIMITS.get(var)
            if soft:
                suspicious_low = (series < soft[0]) & (qc == "VALID")
                suspicious_high = (series > soft[1]) & (qc == "VALID")
                qc[suspicious_low | suspicious_high] = "SUSPICIOUS"

            qc_cols[f"qc_{var}"] = qc

        if qc_cols:
            self._qc = pd.DataFrame(qc_cols, index=self._df.index)
            # Summary
            for qc_col in self._qc.columns:
                counts = self._qc[qc_col].value_counts().to_dict()
                logger.info("QC %s: %s", qc_col, counts)

    def _report_temporal_extent(self):
        if self._df is None:
            return
        ts_col = find_column(self._df, "timestamp") or find_column(self._df, "date")
        if ts_col is None:
            return
        dates = pd.to_datetime(self._df[ts_col], errors="coerce").dropna()
        if not dates.empty:
            self.report.temporal_extent = {
                "start_date": str(dates.min().date()),
                "end_date": str(dates.max().date()),
            }
            logger.info("Temporal extent: %s", self.report.temporal_extent)

    def _report_spatial_extent(self):
        if self._df is None:
            return
        lat_col = find_column(self._df, "latitude")
        lon_col = find_column(self._df, "longitude")
        if lat_col and lon_col:
            lats = pd.to_numeric(self._df[lat_col], errors="coerce").dropna()
            lons = pd.to_numeric(self._df[lon_col], errors="coerce").dropna()
            if not lats.empty and not lons.empty:
                self.report.spatial_extent = {
                    "min_lat": float(lats.min()),
                    "max_lat": float(lats.max()),
                    "min_lon": float(lons.min()),
                    "max_lon": float(lons.max()),
                }
        self.report.crs_detected = self.source_config.get("crs", "EPSG:4326")

    def _save_processed(self):
        if self._df is None or self._df.empty:
            self.report.add_warning("No data to save")
            return
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        out = self.processed_dir / f"{self.input_path.stem}_processed.csv"
        # Attach QC columns if available
        df_out = self._df.copy()
        if self._qc is not None:
            df_out = pd.concat([df_out, self._qc], axis=1)
        df_out.to_csv(out, index=False)
        logger.info("Processed observations saved: %s", out)

    def _save_qc_report(self):
        """Save a separate QC summary report."""
        if self._qc is None:
            return
        qc_summary = {}
        for col in self._qc.columns:
            qc_summary[col] = self._qc[col].value_counts().to_dict()

        import json
        qc_path = self.project_root / "data" / "metadata" / "qc_report_observations.json"
        qc_path.parent.mkdir(parents=True, exist_ok=True)
        with open(qc_path, "w", encoding="utf-8") as fh:
            json.dump(qc_summary, fh, indent=2)
        logger.info("QC report saved: %s", qc_path)
