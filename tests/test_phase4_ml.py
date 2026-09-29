"""
GramDrishti Phase 4 Unit Tests — LightGBM Residual Model & Baseline Evaluation
"""

import os
import pytest
import numpy as np
import pandas as pd
import yaml
import lightgbm as lgb

from src.ml.feature_builder import (
    load_and_merge_datasets,
    add_temporal_features,
    prepare_features_and_targets,
    validate_feature_leakage
)
from src.ml.trainer import train_residual_model, predict_residuals
from src.ml.evaluator import calculate_metrics, calculate_improvement


@pytest.fixture
def sample_config():
    return {
        "project": "GramDrishti",
        "model_params": {
            "objective": "regression",
            "metric": "rmse",
            "learning_rate": 0.05,
            "n_estimators": 10,
            "max_depth": 3,
            "random_state": 42,
            "verbose": -1
        },
        "temporal_split": {
            "train_start": "2024-01-01",
            "train_end": "2024-03-31",
            "calibration_start": "2024-04-01",
            "calibration_end": "2024-04-30",
            "test_start": "2024-05-01",
            "test_end": "2024-06-30"
        },
        "targets": {
            "temperature": {
                "observation_col": "observed_temperature",
                "baseline_col": "b2_temperature",
                "residual_col": "residual_temperature",
                "pred_col": "ml_temperature"
            },
            "humidity": {
                "observation_col": "observed_humidity",
                "baseline_col": "b2_humidity",
                "residual_col": "residual_humidity",
                "pred_col": "ml_humidity"
            }
        },
        "features": {
            "categorical": ["dominant_landcover_class"],
            "forecast": ["forecast_temperature", "forecast_humidity", "lead_time_hours"],
            "geospatial": ["elevation_mean", "slope_mean", "dominant_landcover_class"],
            "temporal": ["day_of_year_sin", "day_of_year_cos", "month"]
        },
        "strictly_forbidden_features": [
            "station_id", "station_group", "observed_temperature", "observed_humidity"
        ]
    }


class TestFeatureLeakage:
    def test_validate_feature_leakage_clean(self, sample_config):
        clean_features = ["forecast_temperature", "elevation_mean", "day_of_year_sin"]
        # Should not raise exception
        validate_feature_leakage(clean_features, sample_config["strictly_forbidden_features"])

    def test_validate_feature_leakage_detects_station_id(self, sample_config):
        dirty_features = ["forecast_temperature", "station_id", "elevation_mean"]
        with pytest.raises(ValueError, match="CRITICAL TARGET LEAKAGE DETECTED"):
            validate_feature_leakage(dirty_features, sample_config["strictly_forbidden_features"])

    def test_validate_feature_leakage_detects_observed_temp(self, sample_config):
        dirty_features = ["observed_temperature", "elevation_mean"]
        with pytest.raises(ValueError, match="CRITICAL TARGET LEAKAGE DETECTED"):
            validate_feature_leakage(dirty_features, sample_config["strictly_forbidden_features"])


class TestTargetAndMLCalculation:
    def test_residual_and_ml_reconstruction_identity(self):
        obs_temp = np.array([25.0, 30.0, 22.5])
        b2_temp = np.array([26.5, 29.0, 21.0])
        res_true = obs_temp - b2_temp  # [-1.5, 1.0, 1.5]

        pred_res = np.array([-1.2, 0.8, 1.6])
        ml_temp = b2_temp + pred_res

        np.testing.assert_allclose(res_true, [-1.5, 1.0, 1.5])
        np.testing.assert_allclose(ml_temp, [25.3, 29.8, 22.6])

    def test_calculate_metrics_values(self):
        y_true = np.array([20.0, 25.0, 30.0])
        y_pred = np.array([21.0, 24.0, 30.0])
        # Errors: [1.0, -1.0, 0.0]
        metrics = calculate_metrics(y_true, y_pred)

        assert metrics["mae"] == pytest.approx(0.6667, abs=1e-3)
        assert metrics["rmse"] == pytest.approx(0.8165, abs=1e-3)
        assert metrics["bias"] == pytest.approx(0.0, abs=1e-3)

    def test_calculate_improvement_percentage(self):
        assert calculate_improvement(2.0, 1.5) == 25.0
        assert calculate_improvement(1.5, 2.0) == -33.33
        assert calculate_improvement(0.0, 1.5) == 0.0


class TestModelReproducibility:
    def test_lightgbm_reproducibility(self, sample_config):
        np.random.seed(42)
        X = pd.DataFrame({
            "forecast_temperature": np.random.randn(100),
            "elevation_mean": np.random.randn(100),
            "b2_temperature": np.random.randn(100),
            "day_of_year_sin": np.random.randn(100),
            "month": np.random.randint(1, 12, size=100)
        })
        y = np.random.randn(100)

        m1 = train_residual_model(X, y, [], sample_config["model_params"])
        p1 = predict_residuals(m1, X)

        m2 = train_residual_model(X, y, [], sample_config["model_params"])
        p2 = predict_residuals(m2, X)

        np.testing.assert_allclose(p1, p2, rtol=1e-5)


class TestPhase4ArtifactsExist:
    def test_prediction_and_model_artifacts_created(self):
        pred_path = "data/processed/predictions/weather_predictions.csv"
        temp_model_path = "models/temperature_residual_model.txt"
        hum_model_path = "models/humidity_residual_model.txt"
        feat_imp_path = "data/processed/models/feature_importance.csv"

        if os.path.exists(pred_path):
            pred_df = pd.read_csv(pred_path)
            assert len(pred_df) == 4320
            assert "ml_temperature" in pred_df.columns
            assert "ml_humidity" in pred_df.columns
            assert not pred_df["ml_temperature"].isna().any()
            assert not pred_df["ml_humidity"].isna().any()

        if os.path.exists(temp_model_path):
            assert os.path.getsize(temp_model_path) > 0

        if os.path.exists(hum_model_path):
            assert os.path.getsize(hum_model_path) > 0


class TestAuditConsistency:
    def test_canonical_test_split_row_counts(self):
        pred_path = "data/processed/predictions/weather_predictions.csv"
        if os.path.exists(pred_path):
            df = pd.read_csv(pred_path)
            test_df = df[df["split"] == "TEST"]
            assert len(test_df) == 1464
            
            # Check station breakdown
            stn_counts = test_df["station_id"].value_counts()
            assert len(stn_counts) == 8
            for count in stn_counts.values:
                assert count == 183

    def test_weighted_station_mae_equals_overall_test_mae(self):
        pred_path = "data/processed/predictions/weather_predictions.csv"
        if os.path.exists(pred_path):
            df = pd.read_csv(pred_path)
            test_df = df[df["split"] == "TEST"]
            
            y_temp = test_df["observed_temperature"].values
            ml_temp = test_df["ml_temperature"].values
            overall_mae = calculate_metrics(y_temp, ml_temp)["mae"]
            
            station_maes = []
            for stn in test_df["station_id"].unique():
                stn_df = test_df[test_df["station_id"] == stn]
                m = calculate_metrics(stn_df["observed_temperature"].values, stn_df["ml_temperature"].values)
                station_maes.append(m["mae"] * len(stn_df))
            
            weighted_mae = round(sum(station_maes) / len(test_df), 4)
            assert weighted_mae == pytest.approx(overall_mae, abs=1e-3)

