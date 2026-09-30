"""
GramDrishti — Phase 8 Application & Read-Only Integrity Tests
==============================================================
Tests for:
1. Application imports successfully.
2. Existing forecast data loads.
3. Panchayat list is generated dynamically (180 panchayats).
4. Missing Phase 7 data does not crash application.
5. Missing optional columns are handled gracefully.
6. Temperature P10/P50/P90 display correctly.
7. Humidity range validation works [0, 100].
8. Rainfall probabilities remain in [0, 1].
9. NOT_EVALUABLE rainfall remains null / None (no false zeros).
10. Panchayat unresolved status is preserved (SUBGRID_RANGE_UNRESOLVED).
11. Invalid data is withheld.
12. Lead-time selection works (24, 48, 72).
13. No previous-phase files are modified by application execution (Hash validation).
"""

import os
import hashlib
import tempfile
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from app.data_loader import DataLoader
from app.services import ForecastService
from app.schemas import (
    validate_temperature,
    validate_humidity,
    validate_probability,
    validate_uncertainty_ordering,
    validate_panchayat_id,
    FreshnessStatus,
    AggregationStatus,
)
from app.formatting import (
    format_temperature,
    format_humidity,
    format_interval,
    format_probability,
    generate_ascii_prob_bar,
    get_badge_html,
    get_reliability_badge,
    get_status_badge,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def get_directory_hashes(directories):
    """Computes SHA256 hashes of all files in given directory list."""
    hashes = {}
    for d in directories:
        dir_path = BASE_DIR / d
        if not dir_path.is_dir():
            continue
        for root, _, files in os.walk(dir_path):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(BASE_DIR).as_posix()
                # Skip pycache and temporary files
                if "__pycache__" in rel_path or rel_path.endswith(".pyc"):
                    continue
                with open(full_path, "rb") as f:
                    hashes[rel_path] = hashlib.sha256(f.read()).hexdigest()
    return hashes


class TestPhase8Application:
    """Complete Phase 8 test suite."""

    def test_01_imports(self):
        """1. Verify application imports and components without errors."""
        import app
        from app.data_loader import DataLoader
        from app.services import ForecastService
        from app.schemas import PanchayatInfo, WeatherForecastData, RainfallForecastData
        from app.components.header import render_header
        from app.components.forecast_cards import render_forecast_cards
        from app.components.rainfall import render_rainfall_section
        from app.components.uncertainty import render_uncertainty_section
        from app.components.advisory import render_advisory_section
        from app.components.reliability import render_reliability_section
        from app.components.map_view import render_map_view
        assert app.__version__ == "1.0.0"

    def test_02_forecast_data_loading(self):
        """2. Existing forecast data loads correctly."""
        loader = DataLoader(BASE_DIR)
        w_df = loader.load_weather_forecasts_df()
        assert not w_df.empty, "Weather predictions dataset should not be empty"
        assert "ml_temperature" in w_df.columns
        assert "ml_humidity" in w_df.columns

        r_df = loader.load_panchayat_rainfall_df()
        assert not r_df.empty, "Rainfall predictions dataset should not be empty"
        assert "rain_probability_1mm" in r_df.columns

    def test_03_panchayat_list_dynamic(self):
        """3. Panchayat list is generated dynamically from data (180 Panchayats)."""
        loader = DataLoader(BASE_DIR)
        panchayats = loader.load_panchayats()
        assert len(panchayats) == 180, f"Expected 180 panchayats, found {len(panchayats)}"
        # Verify IDs are unique
        ids = [p.panchayat_id for p in panchayats]
        assert len(ids) == len(set(ids)), "Panchayat IDs must be unique"
        # Check first entry
        assert panchayats[0].panchayat_name != ""
        assert panchayats[0].block_name != ""

    def test_04_missing_phase7_graceful(self):
        """4. Missing Phase 7 data does not crash application."""
        loader = DataLoader(BASE_DIR)
        p7_rel = loader.load_phase7_reliability()
        assert p7_rel is None, "Phase 7 reliability should be None when file is absent"
        p7_adv = loader.load_phase7_advisories()
        assert p7_adv is None, "Phase 7 advisories should be None when file is absent"

        service = ForecastService(loader)
        view_data = service.get_panchayat_view_data("GP_33_12_0001", lead_time=24)
        assert view_data["phase7_reliability"] is None
        assert view_data["phase7_advisory"] is None
        assert view_data["weather_forecast"] is not None

    def test_05_missing_optional_columns(self):
        """5. Missing optional columns are handled gracefully."""
        loader = DataLoader(BASE_DIR)
        # Test station weather forecast with arbitrary dummy DF missing optional cols
        df_dummy = pd.DataFrame({
            "station_id": ["STN_DUMMY"],
            "observation_time": ["2024-05-01"],
            "valid_time": ["2024-05-02"],
            "lead_time_hours": [24],
            "ml_temperature": [28.5],
            "ml_humidity": [65.0],
        })
        # Mock load_weather_forecasts_df
        loader.load_weather_forecasts_df = lambda: df_dummy
        fc = loader.get_station_weather_forecast("STN_DUMMY", "2024-05-01", 24)
        assert fc is not None
        assert fc.ml_temperature == 28.5
        assert fc.b0_temperature is None
        assert fc.q10_temperature is None
        assert fc.is_valid is True

    def test_06_temperature_p10_p50_p90(self):
        """6. Temperature P10/P50/P90 display and order correctly."""
        loader = DataLoader(BASE_DIR)
        service = ForecastService(loader)
        stns = loader.load_stations_metadata()
        assert len(stns) > 0
        stn_id = stns[0]["station_id"]

        dates = service.get_available_dates()
        fc = loader.get_station_weather_forecast(stn_id, timestamp=dates[-1], lead_time=24)
        assert fc is not None
        assert fc.q10_temperature is not None
        assert fc.q50_temperature is not None
        assert fc.q90_temperature is not None
        assert fc.q10_temperature <= fc.q50_temperature <= fc.q90_temperature

    def test_07_humidity_range_validation(self):
        """7. Humidity range validation works (0 to 100)."""
        assert validate_humidity(50.0).is_valid is True
        assert validate_humidity(0.0).is_valid is True
        assert validate_humidity(100.0).is_valid is True
        assert validate_humidity(-5.0).is_valid is False
        assert validate_humidity(105.0).is_valid is False
        assert validate_humidity("invalid").is_valid is False

    def test_08_rainfall_probability_bounds(self):
        """8. Rainfall probabilities remain in [0, 1]."""
        loader = DataLoader(BASE_DIR)
        df_pr = loader.load_panchayat_rainfall_df()
        assert (df_pr["rain_probability_1mm"] >= 0.0).all()
        assert (df_pr["rain_probability_1mm"] <= 1.0).all()
        assert (df_pr["rain_probability_1mm_p10"] >= 0.0).all()
        assert (df_pr["rain_probability_1mm_p90"] <= 1.0).all()

    def test_09_not_evaluable_rainfall_remains_null(self):
        """9. NOT_EVALUABLE rainfall thresholds (10mm and 25mm) remain null / None."""
        loader = DataLoader(BASE_DIR)
        rain_fc = loader.get_panchayat_rainfall_forecast("GP_33_12_0001", lead_time=24)
        assert rain_fc is not None
        # Must be strictly None
        assert rain_fc.rain_probability_10mm is None
        assert rain_fc.rain_probability_25mm is None
        assert rain_fc.is_evaluable_10mm is False
        assert rain_fc.is_evaluable_25mm is False

        # Format function must return 'Not evaluable' rather than '0.0%'
        assert format_probability(rain_fc.rain_probability_10mm, is_evaluable=False) == "Not evaluable"
        assert format_probability(rain_fc.rain_probability_25mm, is_evaluable=False) == "Not evaluable"
        assert generate_ascii_prob_bar(rain_fc.rain_probability_25mm, is_evaluable=False) == "Not evaluable"

    def test_10_panchayat_unresolved_status(self):
        """10. Panchayat unresolved status is preserved for known boundary edge cases."""
        loader = DataLoader(BASE_DIR)
        df_pr = loader.load_panchayat_rainfall_df()
        unresolved_ids = df_pr[df_pr["aggregation_status"] == "SUBGRID_RANGE_UNRESOLVED"]["panchayat_id"].unique()
        assert len(unresolved_ids) > 0, "SUBGRID_RANGE_UNRESOLVED status must exist in dataset"
        assert "GP_33_12_0114" in unresolved_ids or "GP_33_12_0165" in unresolved_ids

        unres_fc = loader.get_panchayat_rainfall_forecast(unresolved_ids[0], lead_time=24)
        assert unres_fc is not None
        assert unres_fc.aggregation_status == "SUBGRID_RANGE_UNRESOLVED"

    def test_11_invalid_data_withheld(self):
        """11. Invalid data is withheld rather than silently rendered."""
        # Quantile ordering violation
        v_ord = validate_uncertainty_ordering(35.0, 30.0, 40.0)
        assert v_ord.is_valid is False

        # Out-of-bounds temperature
        v_temp = validate_temperature(150.0)
        assert v_temp.is_valid is False

        # Out-of-bounds humidity
        v_hum = validate_humidity(-10.0)
        assert v_hum.is_valid is False

    def test_12_lead_time_selection(self):
        """12. Lead-time selection works across 24, 48, 72 hours."""
        loader = DataLoader(BASE_DIR)
        service = ForecastService(loader)
        available_lt = service.get_available_lead_times()
        assert available_lt == [24, 48, 72]

        for lt in [24, 48, 72]:
            data = service.get_panchayat_view_data("GP_33_12_0001", lead_time=lt)
            assert data["lead_time"] == lt
            assert data["rainfall_forecast"] is not None
            assert data["rainfall_forecast"].lead_time == lt

    def test_13_critical_non_modification(self):
        """13. Critical Non-Modification Verification: verifies hashes of all previous phase files."""
        protected_dirs = ["models", "data/processed", "data/metadata", "configs", "src"]
        hashes_before = get_directory_hashes(protected_dirs)

        # Run DataLoader and ForecastService operations simulating full UI workflow
        loader = DataLoader(BASE_DIR)
        panchayats = loader.load_panchayats()
        service = ForecastService(loader)

        for p in panchayats[:10]:
            for lt in [24, 48, 72]:
                _ = service.get_panchayat_view_data(p.panchayat_id, lead_time=lt)

        _ = loader.get_system_status()
        _ = loader.load_model_performance()
        _ = loader.load_geojson()

        hashes_after = get_directory_hashes(protected_dirs)

        # Check all protected files
        assert hashes_before == hashes_after, "Application execution modified previous-phase artifacts!"
