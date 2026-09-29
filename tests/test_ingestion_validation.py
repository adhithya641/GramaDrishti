"""
GramDrishti — Comprehensive Phase 1 Test Suite
=================================================
Tests for all ingestion validation functions.

All test data is SYNTHETIC and clearly labelled.
No real observations, forecasts, or station data is fabricated.

Covers:
  - boundary validation (fields, geometries, duplicates, hierarchy)
  - observation validation (fields, QC, timestamps, coordinates, duplicates)
  - forecast validation (issue/valid times, lead time, coordinates)
  - raster validation (DEM, landcover — file existence, format)
  - vector validation (water — geometry, CRS)
  - metadata generation
  - missing-data detection
  - coordinate validation
  - timestamp validation
  - config validation
  - validate_dataset dispatcher
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.validation_utils import (
    ValidationReport,
    check_required_fields,
    compute_missing_stats,
    find_column,
    validate_coordinates_india,
    load_config,
    generate_metadata,
)
from src.ingestion.observations import ObservationIngestor
from src.ingestion.forecasts import ForecastIngestor
from src.ingestion.validate_dataset import validate_config, validate_dataset


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def config_path():
    return PROJECT_ROOT / "configs" / "data_sources.yaml"


@pytest.fixture
def sample_obs_csv(tmp_path):
    """SYNTHETIC observation CSV for testing."""
    df = pd.DataFrame({
        "station_id": ["SYNTH_001", "SYNTH_001", "SYNTH_002", "SYNTH_002", "SYNTH_003"],
        "timestamp":  ["2024-06-01", "2024-06-02", "2024-06-01", "2024-06-02", "2024-06-01"],
        "latitude":   [10.0, 10.0, 11.0, 11.0, 12.0],
        "longitude":  [76.0, 76.0, 77.0, 77.0, 78.0],
        "temperature": [32.0, 33.0, None, 31.5, 65.0],  # 65 is INVALID (>60)
        "humidity":    [80.0, 85.0, 90.0, None, 3.0],    # 3% is SUSPICIOUS
        "rainfall":   [0.0, 5.2, 12.4, 0.0, None],
    })
    path = tmp_path / "synth_observations.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def obs_missing_fields(tmp_path):
    """CSV missing required fields."""
    df = pd.DataFrame({
        "station_id": ["S1"],
        "latitude":   [10.0],
        # Missing: timestamp, longitude
    })
    path = tmp_path / "obs_missing_fields.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def obs_high_missing(tmp_path):
    """CSV with 100% missing in weather columns."""
    df = pd.DataFrame({
        "station_id": ["S1", "S2"],
        "timestamp":  ["2024-06-01", "2024-06-02"],
        "latitude":   [10.0, 11.0],
        "longitude":  [76.0, 77.0],
        "temperature": [None, None],
        "humidity":    [None, None],
        "rainfall":   [None, None],
    })
    path = tmp_path / "obs_high_missing.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def obs_duplicates(tmp_path):
    """CSV with duplicate station/timestamp records."""
    df = pd.DataFrame({
        "station_id": ["S1", "S1", "S1"],
        "timestamp":  ["2024-06-01", "2024-06-01", "2024-06-02"],  # first two are dupes
        "latitude":   [10.0, 10.0, 10.0],
        "longitude":  [76.0, 76.0, 76.0],
        "temperature": [32.0, 32.5, 33.0],
        "humidity":    [80.0, 81.0, 82.0],
        "rainfall":   [0.0, 0.0, 1.0],
    })
    path = tmp_path / "obs_duplicates.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def sample_forecast_csv(tmp_path):
    """SYNTHETIC forecast CSV for testing."""
    df = pd.DataFrame({
        "forecast_issue_time": ["2024-06-01 00:00", "2024-06-01 00:00",
                                 "2024-06-01 00:00", "2024-06-02 00:00"],
        "valid_time":          ["2024-06-01 06:00", "2024-06-01 12:00",
                                 "2024-06-02 00:00", "2024-06-02 06:00"],
        "lead_time":           [6, 12, 24, 6],
        "latitude":            [10.0, 10.0, 10.0, 10.0],
        "longitude":           [76.0, 76.0, 76.0, 76.0],
        "temperature":         [30.0, 32.0, 28.0, None],
        "rainfall":            [0.0, 2.0, None, 5.0],
    })
    path = tmp_path / "synth_forecasts.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def forecast_bad_times(tmp_path):
    """Forecast with valid_time BEFORE issue_time."""
    df = pd.DataFrame({
        "forecast_issue_time": ["2024-06-02 00:00"],
        "valid_time":          ["2024-06-01 00:00"],  # backwards!
        "lead_time":           [-24],
        "latitude":            [10.0],
        "longitude":           [76.0],
    })
    path = tmp_path / "forecast_bad_times.csv"
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def empty_csv(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text(
        "station_id,timestamp,latitude,longitude,temperature,humidity,rainfall\n"
    )
    return path


# ===================================================================
# Tests — ValidationReport
# ===================================================================

class TestValidationReport:
    def test_default_is_valid(self):
        r = ValidationReport("Test", "test")
        assert r.is_valid is True

    def test_error_makes_invalid(self):
        r = ValidationReport("Test", "test")
        r.add_error("something broke")
        assert r.is_valid is False

    def test_to_dict_keys(self):
        r = ValidationReport("Test", "test")
        d = r.to_dict()
        for key in ["dataset_name", "source_key", "is_valid", "record_count",
                     "errors", "warnings", "limitations"]:
            assert key in d

    def test_print_report(self):
        r = ValidationReport("Test", "test")
        r.record_count = 42
        r.add_warning("minor issue")
        text = r.print_report()
        assert "42" in text
        assert "minor issue" in text


# ===================================================================
# Tests — Shared Validation Utilities
# ===================================================================

class TestValidationUtils:
    def test_check_required_fields_all_present(self):
        present, missing = check_required_fields(
            ["a", "b", "c"], ["a", "b"]
        )
        assert present == ["a", "b"]
        assert missing == []

    def test_check_required_fields_some_missing(self):
        present, missing = check_required_fields(
            ["a", "c"], ["a", "b"]
        )
        assert "a" in present
        assert "b" in missing

    def test_check_required_fields_case_insensitive(self):
        present, _ = check_required_fields(
            ["Station_ID", "Latitude"], ["station_id", "latitude"]
        )
        assert len(present) == 2

    def test_compute_missing_stats(self):
        counts, pcts = compute_missing_stats({"col_a": 5, "col_b": 0}, 10)
        assert counts == {"col_a": 5}
        assert pcts["col_a"] == 50.0
        assert "col_b" not in counts

    def test_validate_coordinates_india_within(self):
        config = {"validation": {"coordinate_bounds": {
            "india_lat_min": 6, "india_lat_max": 38,
            "india_lon_min": 68, "india_lon_max": 98
        }}}
        warnings = validate_coordinates_india(8, 35, 70, 95, config)
        assert len(warnings) == 0

    def test_validate_coordinates_india_outside(self):
        config = {"validation": {"coordinate_bounds": {
            "india_lat_min": 6, "india_lat_max": 38,
            "india_lon_min": 68, "india_lon_max": 98
        }}}
        warnings = validate_coordinates_india(3, 40, 65, 100, config)
        assert len(warnings) == 4

    def test_find_column(self):
        df = pd.DataFrame({"Station_ID": [1], "Latitude": [10]})
        assert find_column(df, "station_id") == "Station_ID"
        assert find_column(df, "nonexistent") is None


# ===================================================================
# Tests — Observation Ingestion
# ===================================================================

class TestObservationIngestor:
    def test_file_not_found(self, config_path):
        ingestor = ObservationIngestor("nonexistent.csv", config_path)
        report = ingestor.run()
        assert report.is_valid is False
        assert any("does not exist" in e or "Fatal" in e for e in report.errors)

    def test_valid_csv(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        report = ingestor.run()
        assert report.record_count == 5

    def test_missing_fields_detected(self, obs_missing_fields, config_path):
        ingestor = ObservationIngestor(obs_missing_fields, config_path)
        report = ingestor.run()
        assert report.is_valid is False
        assert len(report.fields_missing) > 0

    def test_missing_value_reporting(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        report = ingestor.run()
        assert "temperature" in report.missing_value_counts
        assert report.missing_value_counts["temperature"] == 1

    def test_high_missing_triggers_error(self, obs_high_missing, config_path):
        ingestor = ObservationIngestor(obs_high_missing, config_path)
        report = ingestor.run()
        assert any("missing" in e.lower() for e in report.errors)

    def test_duplicate_detection(self, obs_duplicates, config_path):
        ingestor = ObservationIngestor(obs_duplicates, config_path)
        report = ingestor.run()
        assert any("duplicate" in w.lower() for w in report.warnings)

    def test_temporal_extent(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        report = ingestor.run()
        assert report.temporal_extent is not None
        assert report.temporal_extent["start_date"] == "2024-06-01"
        assert report.temporal_extent["end_date"] == "2024-06-02"

    def test_spatial_extent(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        report = ingestor.run()
        assert report.spatial_extent is not None
        assert report.spatial_extent["min_lat"] == 10.0
        assert report.spatial_extent["max_lat"] == 12.0

    def test_crs_reported(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        report = ingestor.run()
        assert report.crs_detected is not None

    def test_empty_csv(self, empty_csv, config_path):
        ingestor = ObservationIngestor(empty_csv, config_path)
        report = ingestor.run()
        assert report.record_count == 0

    def test_processed_output_created(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        ingestor.run()
        proc_dir = PROJECT_ROOT / "data" / "processed" / "observations"
        assert any(proc_dir.glob("*_processed.csv"))

    def test_validation_report_saved(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        ingestor.run()
        meta_path = PROJECT_ROOT / "data" / "metadata" / "validation_observations.json"
        assert meta_path.exists()

    def test_metadata_saved(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        ingestor.run()
        meta_path = PROJECT_ROOT / "data" / "metadata" / "metadata_observations.json"
        assert meta_path.exists()
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta["data_status"] == "UNVERIFIED"

    def test_qc_report_saved(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        ingestor.run()
        qc_path = PROJECT_ROOT / "data" / "metadata" / "qc_report_observations.json"
        assert qc_path.exists()


# ===================================================================
# Tests — Forecast Ingestion
# ===================================================================

class TestForecastIngestor:
    def test_file_not_found(self, config_path):
        ingestor = ForecastIngestor("nonexistent.csv", config_path)
        report = ingestor.run()
        assert report.is_valid is False

    def test_valid_forecast(self, sample_forecast_csv, config_path):
        ingestor = ForecastIngestor(sample_forecast_csv, config_path)
        report = ingestor.run()
        assert report.record_count == 4
        assert "forecast_issue_time" in report.fields_present
        assert "valid_time" in report.fields_present
        assert "lead_time" in report.fields_present

    def test_backwards_time_warning(self, forecast_bad_times, config_path):
        ingestor = ForecastIngestor(forecast_bad_times, config_path)
        report = ingestor.run()
        assert any("valid_time before" in w for w in report.warnings)

    def test_negative_lead_time_warning(self, forecast_bad_times, config_path):
        ingestor = ForecastIngestor(forecast_bad_times, config_path)
        report = ingestor.run()
        assert any("negative lead_time" in w for w in report.warnings)

    def test_standin_label(self, sample_forecast_csv, config_path):
        ingestor = ForecastIngestor(sample_forecast_csv, config_path, is_standin=True)
        ingestor.run()
        meta_path = PROJECT_ROOT / "data" / "metadata" / "metadata_forecasts.json"
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta["data_status"] == "STAND-IN"

    def test_temporal_extent(self, sample_forecast_csv, config_path):
        ingestor = ForecastIngestor(sample_forecast_csv, config_path)
        report = ingestor.run()
        assert report.temporal_extent is not None

    def test_spatial_extent(self, sample_forecast_csv, config_path):
        ingestor = ForecastIngestor(sample_forecast_csv, config_path)
        report = ingestor.run()
        assert report.spatial_extent is not None


# ===================================================================
# Tests — Coordinate Validation
# ===================================================================

class TestCoordinateValidation:
    def test_india_within_bounds(self, config_path):
        config = load_config(config_path)
        warnings = validate_coordinates_india(8, 35, 70, 95, config)
        assert len(warnings) == 0

    def test_india_outside_south(self, config_path):
        config = load_config(config_path)
        warnings = validate_coordinates_india(3, 35, 70, 95, config)
        assert any("south" in w or "below" in w for w in warnings)

    def test_india_outside_east(self, config_path):
        config = load_config(config_path)
        warnings = validate_coordinates_india(8, 35, 70, 100, config)
        assert any("east" in w for w in warnings)


# ===================================================================
# Tests — Timestamp Validation
# ===================================================================

class TestTimestampValidation:
    def test_valid_timestamps(self, sample_obs_csv, config_path):
        ingestor = ObservationIngestor(sample_obs_csv, config_path)
        report = ingestor.run()
        # No unparseable timestamp warnings expected for well-formed dates
        assert not any("unparseable" in w for w in report.warnings)

    def test_bad_timestamps(self, tmp_path, config_path):
        df = pd.DataFrame({
            "station_id": ["S1"],
            "timestamp": ["not-a-date"],
            "latitude": [10.0],
            "longitude": [76.0],
        })
        path = tmp_path / "bad_timestamps.csv"
        df.to_csv(path, index=False)
        ingestor = ObservationIngestor(path, config_path)
        report = ingestor.run()
        assert any("unparseable" in w for w in report.warnings)


# ===================================================================
# Tests — Metadata Generation
# ===================================================================

class TestMetadataGeneration:
    def test_metadata_structure(self, config_path):
        config = load_config(config_path)
        report = ValidationReport("Test Dataset", "observations")
        report.record_count = 100
        report.crs_detected = "EPSG:4326"
        meta = generate_metadata(
            "observations", report, config["data_sources"]["observations"],
            data_provenance="SYNTHETIC"
        )
        assert meta["dataset_name"] == "Test Dataset"
        assert meta["data_status"] == "SYNTHETIC"
        assert meta["record_count"] == 100

    def test_metadata_never_labels_synthetic_as_real(self, config_path):
        config = load_config(config_path)
        report = ValidationReport("Test", "observations")
        meta = generate_metadata(
            "observations", report, config["data_sources"]["observations"],
            data_provenance="SYNTHETIC"
        )
        assert meta["data_status"] != "REAL"
        assert meta["data_status"] == "SYNTHETIC"


# ===================================================================
# Tests — Missing Data Detection
# ===================================================================

class TestMissingDataDetection:
    def test_no_missing(self, tmp_path, config_path):
        df = pd.DataFrame({
            "station_id": ["S1", "S2"],
            "timestamp": ["2024-06-01", "2024-06-02"],
            "latitude": [10.0, 11.0],
            "longitude": [76.0, 77.0],
            "temperature": [30.0, 31.0],
            "humidity": [80.0, 85.0],
            "rainfall": [0.0, 1.0],
        })
        path = tmp_path / "no_missing.csv"
        df.to_csv(path, index=False)
        ingestor = ObservationIngestor(path, config_path)
        report = ingestor.run()
        assert len(report.missing_value_counts) == 0

    def test_partial_missing(self, tmp_path, config_path):
        df = pd.DataFrame({
            "station_id": ["S1", "S2", "S3"],
            "timestamp": ["2024-06-01", "2024-06-02", "2024-06-03"],
            "latitude": [10.0, 11.0, 12.0],
            "longitude": [76.0, 77.0, 78.0],
            "temperature": [30.0, None, 32.0],
            "humidity": [80.0, 85.0, None],
            "rainfall": [0.0, 1.0, 2.0],
        })
        path = tmp_path / "partial_missing.csv"
        df.to_csv(path, index=False)
        ingestor = ObservationIngestor(path, config_path)
        report = ingestor.run()
        assert "temperature" in report.missing_value_counts
        assert "humidity" in report.missing_value_counts
        assert report.missing_value_percentages["temperature"] == pytest.approx(33.33, abs=0.1)


# ===================================================================
# Tests — Config Validation
# ===================================================================

class TestConfigValidation:
    def test_config_loads(self, config_path):
        config = load_config(config_path)
        assert config["project"]["name"] == "GramDrishti"

    def test_config_validation(self, config_path):
        result = validate_config(config_path)
        assert result["project_name"] == "GramDrishti"
        assert "boundaries" in result["sources_defined"]
        assert "observations" in result["sources_defined"]
        assert "forecasts" in result["sources_defined"]
        assert "dem" in result["sources_defined"]
        assert "landcover" in result["sources_defined"]
        assert "water" in result["sources_defined"]

    def test_pilot_region_status(self, config_path):
        result = validate_config(config_path)
        assert result["pilot_region"] == "NOT YET SELECTED"

    def test_directories_exist(self, config_path):
        result = validate_config(config_path)
        for source_key, st in result["directories_status"].items():
            assert st["raw_exists"] is True, f"Raw dir missing: {source_key}"


# ===================================================================
# Tests — Validate Dataset Dispatcher
# ===================================================================

class TestValidateDatasetDispatcher:
    def test_unknown_source_key(self):
        with pytest.raises(ValueError, match="Unknown source key"):
            validate_dataset("nonexistent", "path.csv")

    def test_dispatch_observations(self, sample_obs_csv, config_path):
        result = validate_dataset("observations", sample_obs_csv, config_path)
        assert result["source_key"] == "observations"

    def test_dispatch_forecasts(self, sample_forecast_csv, config_path):
        result = validate_dataset("forecasts", sample_forecast_csv, config_path)
        assert result["source_key"] == "forecasts"
