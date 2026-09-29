"""
Tests for Phase 5 Uncertainty Quantification
"""
import os
import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
import json
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.uncertainty.conformal import classify_reliability

@pytest.fixture(scope="module")
def unc_config():
    with open("configs/uncertainty_config.yaml", "r") as f:
        return yaml.safe_load(f)

@pytest.fixture(scope="module")
def predictions(unc_config):
    return pd.read_csv(unc_config["paths"]["uncertainty_predictions_csv"])

@pytest.fixture(scope="module")
def metrics(unc_config):
    with open(unc_config["paths"]["metrics_json"], "r") as f:
        return json.load(f)

# ===================== Output Existence =====================

def test_phase5_outputs_exist(unc_config):
    pred_file = unc_config["paths"]["uncertainty_predictions_csv"]
    metrics_file = unc_config["paths"]["metrics_json"]
    assert os.path.exists(pred_file), f"Missing {pred_file}"
    assert os.path.exists(metrics_file), f"Missing {metrics_file}"

def test_model_artifacts_exist(unc_config):
    models_dir = unc_config["paths"]["models_dir"]
    for var in ["temp", "hum"]:
        for q in ["lower", "median", "upper"]:
            path = os.path.join(models_dir, f"{var}_{q}.txt")
            assert os.path.exists(path), f"Missing model file: {path}"

# ===================== Quantile Ordering =====================

def test_quantile_ordering_temperature(predictions):
    q10 = predictions["q10_temperature"].round(6)
    q50 = predictions["q50_temperature"].round(6)
    q90 = predictions["q90_temperature"].round(6)
    assert (q10 <= q50).all(), "Temperature q10 > q50 violation"
    assert (q50 <= q90).all(), "Temperature q50 > q90 violation"

def test_quantile_ordering_humidity(predictions):
    q10 = predictions["q10_humidity"].round(6)
    q50 = predictions["q50_humidity"].round(6)
    q90 = predictions["q90_humidity"].round(6)
    assert (q10 <= q50).all(), "Humidity q10 > q50 violation"
    assert (q50 <= q90).all(), "Humidity q50 > q90 violation"

# ===================== Physical Bounds =====================

def test_humidity_bounds(predictions):
    assert predictions["q10_humidity"].min() >= 0.0, "Humidity q10 < 0"
    assert predictions["q90_humidity"].max() <= 100.0, "Humidity q90 > 100"
    assert predictions["q50_humidity"].min() >= 0.0, "Humidity q50 < 0"
    assert predictions["q50_humidity"].max() <= 100.0, "Humidity q50 > 100"

# ===================== No NaN =====================

def test_no_nan_in_predictions(predictions):
    q_cols = [c for c in predictions.columns if c.startswith("q10") or c.startswith("q50") or c.startswith("q90")]
    for col in q_cols:
        assert not predictions[col].isna().any(), f"NaN found in {col}"

def test_no_nan_in_interval_widths(predictions):
    assert not predictions["temperature_interval_width"].isna().any()
    assert not predictions["humidity_interval_width"].isna().any()

# ===================== Interval Width Positivity =====================

def test_interval_widths_positive(predictions):
    assert (predictions["temperature_interval_width"] >= 0).all(), "Negative temperature interval width"
    assert (predictions["humidity_interval_width"] >= 0).all(), "Negative humidity interval width"

# ===================== Conformal Calibration Validity =====================

def test_calibration_coverage_near_target(metrics):
    """Calibration coverage should be close to target (80%)."""
    target = metrics["calibration_empirical_coverage"]["target_coverage"]
    temp_cov = metrics["calibration_empirical_coverage"]["temperature"]
    hum_cov = metrics["calibration_empirical_coverage"]["humidity"]
    # Within 5 percentage points of target
    assert abs(temp_cov - target) < 0.05, f"Temp calib coverage {temp_cov:.2%} not near target {target:.0%}"
    assert abs(hum_cov - target) < 0.05, f"Hum calib coverage {hum_cov:.2%} not near target {target:.0%}"

def test_coverage_metrics_populated(metrics):
    cov_temp = metrics["test_empirical_coverage"]["temperature"]
    cov_hum = metrics["test_empirical_coverage"]["humidity"]
    assert cov_temp > 0, "Temp test coverage is 0"
    assert cov_hum > 0, "Humidity test coverage is 0"

# ===================== Record Counts =====================

def test_record_counts(predictions, metrics):
    assert metrics["record_counts"]["total"] == len(predictions)
    test_count = len(predictions[predictions["split"] == "TEST"])
    assert metrics["record_counts"]["test"] == test_count

# ===================== Breakdowns =====================

def test_station_metrics_present(metrics):
    assert "station_level_metrics" in metrics
    assert len(metrics["station_level_metrics"]) > 0

def test_lead_time_metrics_present(metrics):
    assert "lead_time_level_metrics" in metrics
    assert len(metrics["lead_time_level_metrics"]) > 0

# ===================== Reliability Classification =====================

def test_reliability_classification():
    interval_widths = pd.Series([1.0, 4.0, 6.0])
    classifications = classify_reliability(interval_widths, medium_threshold=3.0, low_threshold=5.0)
    assert classifications.iloc[0] == "HIGH"
    assert classifications.iloc[1] == "MEDIUM"
    assert classifications.iloc[2] == "LOW"

def test_reliability_columns_present(predictions):
    assert "temperature_reliability" in predictions.columns
    assert "humidity_reliability" in predictions.columns
    valid_labels = {"HIGH", "MEDIUM", "LOW"}
    assert set(predictions["temperature_reliability"].unique()).issubset(valid_labels)
    assert set(predictions["humidity_reliability"].unique()).issubset(valid_labels)

def test_reliability_distribution_in_metrics(metrics):
    assert "reliability_distribution_test" in metrics
    assert "temperature" in metrics["reliability_distribution_test"]
    assert "humidity" in metrics["reliability_distribution_test"]

# ===================== Distributional Shift Documentation =====================

def test_distributional_shift_documented(metrics):
    assert "distributional_shift_analysis" in metrics
    assert "humidity_residual_mean_test" in metrics["distributional_shift_analysis"]
    assert "note" in metrics["distributional_shift_analysis"]

# ===================== Required Columns =====================

def test_required_columns_present(predictions):
    required = [
        "observation_time", "station_id", "grid_id", "split", "lead_time_hours",
        "observed_temperature", "observed_humidity",
        "b2_temperature", "b2_humidity",
        "ml_temperature", "ml_humidity",
        "q10_temperature", "q50_temperature", "q90_temperature",
        "q10_humidity", "q50_humidity", "q90_humidity",
        "temperature_interval_width", "humidity_interval_width",
        "temperature_reliability", "humidity_reliability"
    ]
    for col in required:
        assert col in predictions.columns, f"Missing column: {col}"
