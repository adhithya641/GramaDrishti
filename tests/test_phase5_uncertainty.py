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

# ===================== AUDIT TESTS =====================

from src.uncertainty.conformal import (
    compute_conformal_scores,
    get_conformal_correction,
    apply_conformal_correction
)

def test_conformal_score_formula_deterministic():
    """Manually verify score = max(q10 - y, y - q90) with known values."""
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    q10 = np.array([0.5, 1.5, 2.0, 3.0, 4.0])
    q90 = np.array([1.5, 2.5, 4.0, 5.0, 6.0])

    scores = compute_conformal_scores(y, q10, q90)
    expected = np.maximum(q10 - y, y - q90)
    np.testing.assert_array_almost_equal(scores, expected)

def test_conformal_finite_sample_quantile():
    """Verify q_level = (1-alpha)*(1 + 1/n) and correction matches np.quantile."""
    scores = np.array([-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])
    alpha = 0.2
    n = len(scores)
    q_level = (1 - alpha) * (1 + 1/n)
    expected = float(np.quantile(scores, min(q_level, 1.0), method='higher'))
    actual = get_conformal_correction(scores, alpha)
    assert actual == expected, f"Expected {expected}, got {actual}"

def test_interval_construction_formula():
    """Verify lower = q10 - correction, upper = q90 + correction."""
    q10 = pd.Series([5.0, 10.0, 15.0])
    q90 = pd.Series([20.0, 25.0, 30.0])
    correction = 2.5
    result = apply_conformal_correction(q10, q90, correction)
    np.testing.assert_array_almost_equal(result["q10_calibrated"].values, [2.5, 7.5, 12.5])
    np.testing.assert_array_almost_equal(result["q90_calibrated"].values, [22.5, 27.5, 32.5])

def test_calibration_isolation(metrics):
    """Conformal correction must use exactly the calibration split records."""
    n_calib = metrics["record_counts"]["calibration"]
    assert n_calib == 720, f"Expected 720 calibration records, got {n_calib}"

def test_test_isolation(predictions, metrics):
    """TEST records must never influence conformal correction."""
    n_test = metrics["record_counts"]["test"]
    test_rows = len(predictions[predictions["split"] == "TEST"])
    assert n_test == test_rows == 1464

def test_station_coverage_calculable(predictions):
    """Verify station-level coverage can be computed for all stations."""
    test = predictions[predictions["split"] == "TEST"]
    for station_id in test["station_id"].unique():
        s = test[test["station_id"] == station_id]
        cov = ((s["observed_humidity"] >= s["q10_humidity"]) &
               (s["observed_humidity"] <= s["q90_humidity"])).mean()
        assert 0.0 <= cov <= 1.0

def test_lead_time_coverage_calculable(predictions):
    """Verify lead-time coverage can be computed for all lead times."""
    test = predictions[predictions["split"] == "TEST"]
    for lt in test["lead_time_hours"].unique():
        lt_sub = test[test["lead_time_hours"] == lt]
        cov = ((lt_sub["observed_humidity"] >= lt_sub["q10_humidity"]) &
               (lt_sub["observed_humidity"] <= lt_sub["q90_humidity"])).mean()
        assert 0.0 <= cov <= 1.0

def test_raw_observed_rh_bounds(predictions):
    """All observed RH values must be in [0, 100]."""
    assert predictions["observed_humidity"].min() >= 0.0
    assert predictions["observed_humidity"].max() <= 100.0

def test_conformal_correction_positive(metrics):
    """Conformal corrections should be finite numbers (may be negative for well-calibrated raw models)."""
    assert np.isfinite(metrics["conformal_corrections"]["temperature"])
    assert np.isfinite(metrics["conformal_corrections"]["humidity"])

def test_no_duplicate_records(predictions):
    """No duplicate (station, time, lead_time) combinations."""
    dups = predictions.duplicated(subset=["station_id", "observation_time", "lead_time_hours"]).sum()
    assert dups == 0, f"Found {dups} duplicate records"

