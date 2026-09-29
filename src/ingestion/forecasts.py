"""
GramDrishti -- Forecast Ingestion
===================================
Ingests coarse-resolution weather forecast data (CSV initially).

CRITICAL DISTINCTIONS preserved:
  - forecast_issue_time : when the forecast was generated
  - valid_time          : what time the forecast is valid for
  - lead_time           : valid_time - forecast_issue_time

Reanalysis data must NOT be treated as historical forecast data.
If a stand-in source is used, it is labelled STAND-IN.
If forecast data is unavailable, status = UNAVAILABLE.

Does NOT fabricate forecasts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

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

logger = logging.getLogger("gramdrishti.ingestion.forecasts")


class ForecastIngestor:
    """
    Ingestor for gridded / tabular weather forecast datasets.

    Parameters
    ----------
    input_path : str | Path
        Path to the raw forecast CSV file.
    config_path : str | Path | None
        Override path to data_sources.yaml.
    is_standin : bool
        If True, label this data as STAND-IN (not real forecast).
    """

    def __init__(
        self,
        input_path: str | Path,
        config_path: str | Path | None = None,
        is_standin: bool = False,
    ):
        self.input_path = Path(input_path)
        self.config = load_config(config_path)
        self.source_config = self.config["data_sources"]["forecasts"]
        self.project_root = get_project_root()
        self.processed_dir = self.project_root / self.source_config["processed_dir"]
        self.is_standin = is_standin
        self.report = ValidationReport(
            dataset_name=self.source_config["dataset_name"],
            source_key="forecasts",
        )
        self._df: Optional[pd.DataFrame] = None

    def run(self) -> ValidationReport:
        logger.info("Starting forecast ingestion from %s", self.input_path)
        try:
            self._validate_file()
            self._load_data()
            self._apply_mapping()
            self._validate_fields()
            self._validate_issue_valid_times()
            self._validate_lead_time()
            self._validate_coordinates()
            self._report_missing_values()
            self._report_spatial_extent()
            self._report_temporal_extent()
            self._report_lead_time_distribution()
            self._save_processed()
        except Exception as exc:
            self.report.add_error(f"Fatal: {exc}")
            logger.error("Forecast ingestion failed: %s", exc, exc_info=True)

        self.report.status = "READY" if self.report.is_valid else "PARTIAL"
        provenance = "STAND-IN" if self.is_standin else "UNVERIFIED"
        save_report(self.report)
        meta = generate_metadata("forecasts", self.report, self.source_config,
                                 data_provenance=provenance)
        meta["original_filename"] = self.input_path.name
        if self.is_standin:
            meta["notes"] = "STAND-IN: " + meta.get("notes", "")
        save_metadata(meta, "forecasts")
        logger.info("Forecast ingestion complete. Valid=%s", self.report.is_valid)
        return self.report

    def _validate_file(self):
        ok, msg = validate_file_exists(self.input_path)
        if not ok:
            raise FileNotFoundError(msg)
        ext = self.input_path.suffix.lstrip(".").lower()
        self.report.file_format = ext

    def _load_data(self):
        self._df = pd.read_csv(self.input_path)
        self.report.record_count = len(self._df)
        logger.info("Loaded %d forecast records", len(self._df))

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

    def _validate_issue_valid_times(self):
        """Ensure forecast_issue_time and valid_time are parseable datetimes."""
        if self._df is None:
            return
        for time_field in ["forecast_issue_time", "valid_time"]:
            col = find_column(self._df, time_field)
            if col is None:
                continue
            parsed = pd.to_datetime(self._df[col], errors="coerce")
            n_bad = int(parsed.isna().sum() - self._df[col].isna().sum())
            if n_bad > 0:
                self.report.add_warning(
                    f"{n_bad} records have unparseable {time_field}"
                )
        # Check valid_time >= issue_time
        issue_col = find_column(self._df, "forecast_issue_time")
        valid_col = find_column(self._df, "valid_time")
        if issue_col and valid_col:
            issue_dt = pd.to_datetime(self._df[issue_col], errors="coerce")
            valid_dt = pd.to_datetime(self._df[valid_col], errors="coerce")
            both_valid = issue_dt.notna() & valid_dt.notna()
            backwards = (valid_dt < issue_dt) & both_valid
            n_backwards = int(backwards.sum())
            if n_backwards > 0:
                self.report.add_warning(
                    f"{n_backwards} records have valid_time before forecast_issue_time"
                )

    def _validate_lead_time(self):
        if self._df is None:
            return
        col = find_column(self._df, "lead_time")
        if col is None:
            return
        lt = pd.to_numeric(self._df[col], errors="coerce")
        n_neg = int((lt < 0).sum())
        if n_neg > 0:
            self.report.add_warning(f"{n_neg} records have negative lead_time")
        n_null = int(lt.isna().sum())
        if n_null > 0:
            self.report.add_warning(f"{n_null} records have null/unparseable lead_time")

    def _validate_coordinates(self):
        if self._df is None:
            return
        lat_col = find_column(self._df, "latitude")
        lon_col = find_column(self._df, "longitude")
        if lat_col and lon_col:
            lats = pd.to_numeric(self._df[lat_col], errors="coerce").dropna()
            lons = pd.to_numeric(self._df[lon_col], errors="coerce").dropna()
            if not lats.empty and not lons.empty:
                for w in validate_coordinates_india(
                    float(lats.min()), float(lats.max()),
                    float(lons.min()), float(lons.max()),
                    self.config,
                ):
                    self.report.add_warning(w)

    def _report_missing_values(self):
        if self._df is None or self._df.empty:
            return
        total = len(self._df)
        raw = {col: int(self._df[col].isna().sum()) for col in self._df.columns}
        counts, pcts = compute_missing_stats(raw, total)
        self.report.missing_value_counts = counts
        self.report.missing_value_percentages = pcts

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

    def _report_temporal_extent(self):
        if self._df is None:
            return
        # Use issue time for temporal extent
        col = find_column(self._df, "forecast_issue_time")
        if col is None:
            col = find_column(self._df, "valid_time")
        if col is None:
            return
        dates = pd.to_datetime(self._df[col], errors="coerce").dropna()
        if not dates.empty:
            self.report.temporal_extent = {
                "start_date": str(dates.min().date()),
                "end_date": str(dates.max().date()),
            }

    def _report_lead_time_distribution(self):
        if self._df is None:
            return
        col = find_column(self._df, "lead_time")
        if col is None:
            return
        lt = pd.to_numeric(self._df[col], errors="coerce").dropna()
        if not lt.empty:
            logger.info(
                "Lead-time distribution: min=%s, max=%s, mean=%.1f, unique=%d",
                lt.min(), lt.max(), lt.mean(), lt.nunique(),
            )

    def _save_processed(self):
        if self._df is None or self._df.empty:
            self.report.add_warning("No data to save")
            return
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        out = self.processed_dir / f"{self.input_path.stem}_processed.csv"
        self._df.to_csv(out, index=False)
        logger.info("Processed forecasts saved: %s", out)
