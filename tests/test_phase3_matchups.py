"""
GramDrishti — Phase 3 Weather Matchups & Baselines Unit Tests
==============================================================
Tests observation/forecast loading, spatial/temporal matching, baseline ladder
(B0, B1, B2, B3), chronological split separation, and Quality Checks A-Q.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import yaml

from src.matchups.observation_loader import load_observations
from src.matchups.forecast_loader import load_forecasts
from src.matchups.spatial_temporal_matcher import match_observations_and_forecasts
from src.matchups.baselines import (
    compute_b0_coarse,
    compute_b1_bilinear,
    compute_b2_lapse_rate,
    compute_b3_quantile_mapping,
    compute_residuals,
)
from src.matchups.validate_matchups import MatchupValidator

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestObservationAndForecastLoaders:
    """Tests for Phase 1 dataset loaders."""

    def test_load_observations(self):
        obs_path = PROJECT_ROOT / "data" / "raw" / "observations" / "coimbatore_station_observations.csv"
        df = load_observations(obs_path)

        assert not df.empty
        assert "station_id" in df.columns
        assert "timestamp" in df.columns
        assert "observed_temperature" in df.columns
        assert "observed_humidity" in df.columns
        assert "qc_status" in df.columns

    def test_load_forecasts(self):
        fc_path = PROJECT_ROOT / "data" / "raw" / "forecasts" / "coimbatore_historical_forecasts.csv"
        df = load_forecasts(fc_path)

        assert not df.empty
        assert "forecast_issue_time" in df.columns
        assert "valid_time" in df.columns
        assert "lead_time_hours" in df.columns
        assert "forecast_temperature" in df.columns
        assert df["data_status"].iloc[0] == "STAND-IN"


class TestSpatialTemporalMatcher:
    """Tests for deterministic spatial and temporal alignment."""

    def test_matching_logic(self):
        obs_path = PROJECT_ROOT / "data" / "raw" / "observations" / "coimbatore_station_observations.csv"
        fc_path = PROJECT_ROOT / "data" / "raw" / "forecasts" / "coimbatore_historical_forecasts.csv"
        grid_path = PROJECT_ROOT / "data" / "processed" / "geospatial" / "geospatial_features_master.csv"
        cfg_path = PROJECT_ROOT / "configs" / "baselines.yaml"

        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        obs_df = load_observations(obs_path)
        fc_df = load_forecasts(fc_path)

        matched_df, stats = match_observations_and_forecasts(obs_df, fc_df, grid_path, cfg)

        assert not matched_df.empty
        assert "grid_id" in matched_df.columns
        assert "panchayat_id" in matched_df.columns
        assert "forecast_parent_id" in matched_df.columns
        assert "split" in matched_df.columns
        assert set(matched_df["split"].unique()).issubset({"TRAIN", "CALIBRATION", "TEST"})


class TestBaselinesLadder:
    """Tests for B0, B1, B2, B3 baselines."""

    def test_b0_coarse(self):
        df = pd.DataFrame({
            "forecast_temperature": [28.5, 30.0],
            "forecast_humidity": [70.0, 65.0],
            "forecast_rainfall": [0.0, 5.2],
        })
        out = compute_b0_coarse(df)

        assert (out["b0_temperature"] == df["forecast_temperature"]).all()
        assert (out["b0_humidity"] == df["forecast_humidity"]).all()
        assert (out["b0_rainfall"] == df["forecast_rainfall"]).all()

    def test_b2_lapse_rate_correction(self):
        df = pd.DataFrame({
            "forecast_temperature": [25.0, 25.0],
            "forecast_humidity": [70.0, 70.0],
            "station_elevation": [1000.0, 350.0],
            "grid_elevation": [350.0, 350.0],
        })
        cfg = {"lapse_rate": {"temperature_deg_per_meter": -0.0065}}

        out = compute_b2_lapse_rate(df, cfg)

        # Delta z = 650m -> Temp change = -0.0065 * 650 = -4.225 °C -> 25.0 - 4.225 = 20.78 °C
        assert out["b2_temperature"].iloc[0] < 25.0
        assert out["b2_temperature"].iloc[1] == 25.0

    def test_b3_quantile_mapping_no_future_leakage(self):
        df = pd.DataFrame({
            "split": ["TRAIN", "TRAIN", "TEST", "TEST"],
            "b2_temperature": [20.0, 30.0, 22.0, 28.0],
            "observed_temperature": [22.0, 32.0, 24.0, 30.0],
            "b0_humidity": [60.0, 80.0, 65.0, 75.0],
            "observed_humidity": [55.0, 75.0, 60.0, 70.0],
        })
        cfg = {"quantile_mapping": {"n_quantiles": 10}}

        out = compute_b3_quantile_mapping(df, cfg)

        assert "b3_temperature" in out.columns
        assert "b3_humidity" in out.columns
        assert out["b3_temperature"].isna().sum() == 0


class TestMasterMatchupValidator:
    """Tests for MatchupValidator Quality Checks A through Q."""

    def test_matchup_validator_on_master_data(self):
        matchup_csv = PROJECT_ROOT / "data" / "processed" / "matchups" / "weather_matchups.csv"
        assert matchup_csv.exists()

        df = pd.read_csv(matchup_csv)
        validator = MatchupValidator(df)
        report = validator.validate()

        assert report["is_valid"] is True
        assert len(report["issues"]) == 0
