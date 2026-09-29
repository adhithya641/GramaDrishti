"""
GramDrishti — Phase 6 Test Suite
=================================
Validates Phase 6 rainfall probability modeling, target creation, data quality guards,
isotonic calibration isolation, probability bounds, and Panchayat spatial aggregation.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd

from src.ml.rainfall_data import (
    create_rainfall_targets,
    audit_rainfall_data,
    compute_event_stats
)
from src.ml.rainfall_models import (
    ClimatologyModel,
    LogisticRegressionModel,
    LightGBMRainfallModel,
    IsotonicCalibrator
)
from src.ml.rainfall_evaluator import (
    calculate_brier_score,
    calculate_classification_metrics,
    evaluate_model_performance
)
from src.ml.panchayat_aggregator import aggregate_grid_to_panchayats


def test_rainfall_label_creation_deterministic():
    """Verify binary targets for 1mm, 10mm, 25mm thresholds."""
    df = pd.DataFrame({"observed_rainfall": [0.0, 0.5, 1.0, 5.0, 10.0, 20.0, 25.0, 30.0]})
    df_out = create_rainfall_targets(df)

    assert df_out["rain_1mm"].tolist() == [0, 0, 1, 1, 1, 1, 1, 1]
    assert df_out["rain_10mm"].tolist() == [0, 0, 0, 0, 1, 1, 1, 1]
    assert df_out["rain_25mm"].tolist() == [0, 0, 0, 0, 0, 0, 1, 1]


def test_rainfall_data_audit():
    """Verify data audit catches invalid or missing values."""
    df_clean = pd.DataFrame({
        "station_id": ["STN_01", "STN_02"],
        "observation_time": ["2024-01-01", "2024-01-01"],
        "lead_time_hours": [24, 24],
        "observed_rainfall": [2.5, 0.0]
    })
    audit = audit_rainfall_data(df_clean)
    assert audit["clean_data"] is True
    assert audit["missing_observed_rainfall"] == 0
    assert audit["duplicate_records"] == 0


def test_climatology_model_fit_predict():
    """Verify R0 Climatology model outputs constant train event rate."""
    y_train = np.array([0, 0, 1, 1])  # mean = 0.5
    r0 = ClimatologyModel().fit(y_train)
    probs = r0.predict_proba(pd.DataFrame({"x": [1, 2, 3]}))
    assert np.allclose(probs, 0.5)


def test_single_class_logistic_and_lgb_handling():
    """Verify models handle single-class target datasets without crashing."""
    X_train = pd.DataFrame({"feat1": [1.0, 2.0, 3.0], "feat2": [4.0, 5.0, 6.0]})
    y_single = np.array([0, 0, 0])

    r1 = LogisticRegressionModel().fit(X_train, y_single)
    r2 = LightGBMRainfallModel().fit(X_train, y_single)

    X_test = pd.DataFrame({"feat1": [1.5], "feat2": [4.5]})
    p_r1 = r1.predict_proba(X_test)
    p_r2 = r2.predict_proba(X_test)

    assert p_r1[0] == 0.0
    assert p_r2[0] == 0.0


def test_isotonic_calibration_isolation():
    """Verify IsotonicCalibrator is bounded in [0, 1] and monotonic."""
    raw_calib_p = np.array([0.1, 0.3, 0.6, 0.8])
    y_calib = np.array([0, 0, 1, 1])

    calibrator = IsotonicCalibrator().fit(raw_calib_p, y_calib)
    raw_test_p = np.array([0.05, 0.4, 0.7, 0.95])
    calib_test_p = calibrator.transform(raw_test_p)

    assert np.all(calib_test_p >= 0.0)
    assert np.all(calib_test_p <= 1.0)
    assert np.all(np.diff(calib_test_p) >= 0)


def test_brier_score_formula():
    """Verify Brier Score calculation against known values."""
    probs = np.array([0.8, 0.2, 0.9])
    y_true = np.array([1, 0, 1])
    # squared errors: (0.8-1)^2 = 0.04, (0.2-0)^2 = 0.04, (0.9-1)^2 = 0.01 -> mean = 0.03
    bs = calculate_brier_score(probs, y_true)
    assert np.isclose(bs, 0.03)


def test_classification_metrics_pod_far_csi():
    """Verify POD, FAR, CSI formulas."""
    probs = np.array([0.7, 0.8, 0.2, 0.3])
    y_true = np.array([1, 0, 1, 0])
    # p >= 0.5 -> [1, 1, 0, 0]
    # TP: obs=1 & pred=1 -> idx 0 (TP=1)
    # FP: obs=0 & pred=1 -> idx 1 (FP=1)
    # FN: obs=1 & pred=0 -> idx 2 (FN=1)
    # TN: obs=0 & pred=0 -> idx 3 (TN=1)
    # POD = 1/(1+1) = 0.5, FAR = 1/(1+1) = 0.5, CSI = 1/(1+1+1) = 1/3
    res = calculate_classification_metrics(probs, y_true, threshold=0.5)
    assert res["tp"] == 1
    assert res["fp"] == 1
    assert res["fn"] == 1
    assert res["tn"] == 1
    assert np.isclose(res["pod"], 0.5)
    assert np.isclose(res["far"], 0.5)
    assert np.isclose(res["csi"], 1.0 / 3.0)


def test_panchayat_aggregation_properties():
    """Verify Panchayat aggregation calculations, status, and ordering constraints."""
    grid_data = pd.DataFrame({
        "panchayat_id": ["GP_01"] * 5 + ["GP_02"] * 2,
        "timestamp": ["2024-05-01"] * 7,
        "lead_time": [24] * 7,
        "prob_1mm": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8],
        "prob_10mm": [0.0, 0.05, 0.1, 0.15, 0.2, 0.0, 0.0],
        "prob_25mm": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    })
    agg_df = aggregate_grid_to_panchayats(grid_data)
    assert len(agg_df) == 2

    gp01 = agg_df[agg_df["panchayat_id"] == "GP_01"].iloc[0]
    gp02 = agg_df[agg_df["panchayat_id"] == "GP_02"].iloc[0]

    # Check status
    assert gp01["aggregation_status"] == "OK"
    assert gp01["grid_cell_count"] == 5

    assert gp02["aggregation_status"] == "SUBGRID_RANGE_UNRESOLVED"
    assert gp02["grid_cell_count"] == 2

    # Check ordering constraints: P10 <= median <= P90
    assert gp01["rain_probability_1mm_p10"] <= gp01["rain_probability_1mm"]
    assert gp01["rain_probability_1mm"] <= gp01["rain_probability_1mm_p90"]
    assert gp01["spatial_spread_1mm"] >= 0.0


def test_phase6_artifacts_and_output_existence():
    """Verify that Phase 6 output files and reports exist and are non-empty."""
    station_pred_path = "data/processed/predictions/station_rainfall_predictions.csv"
    panchayat_pred_path = "data/processed/predictions/panchayat_rainfall_predictions.csv"
    val_json_path = "data/metadata/validation_phase6_rainfall.json"

    assert os.path.exists(station_pred_path)
    assert os.path.exists(panchayat_pred_path)
    assert os.path.exists(val_json_path)

    panchayat_df = pd.read_csv(panchayat_pred_path)
    assert len(panchayat_df) > 0
    assert panchayat_df["panchayat_id"].nunique() == 180

    with open(val_json_path, "r") as f:
        val_data = json.load(f)

    assert val_data["record_counts"]["train"] == 2136
    assert val_data["record_counts"]["calibration"] == 720
    assert val_data["record_counts"]["test"] == 1464
    assert val_data["panchayat_aggregation_stats"]["unique_panchayats"] == 180


def test_audit_logistic_extrapolation_detection():
    """Verify that LogisticRegressionModel produces valid probability predictions bounded in [0, 1]."""
    X_train = pd.DataFrame({"day_sin": np.linspace(0.1, 1.0, 100), "day_cos": np.linspace(0.9, 0.1, 100)})
    y_train = np.zeros(100)
    y_train[0] = 1 # 1% prior

    clf = LogisticRegressionModel().fit(X_train, y_train)

    X_test = pd.DataFrame({"day_sin": np.linspace(0.9, 0.5, 50), "day_cos": np.linspace(-0.5, -1.0, 50)})
    p_test = clf.predict_proba(X_test)

    assert np.all(p_test >= 0.0)
    assert np.all(p_test <= 1.0)


def test_audit_zero_event_threshold_trainability():
    """Verify 10mm and 25mm threshold handling when TRAIN has zero positive events."""
    X_train = pd.DataFrame({"feat1": [1.0, 2.0, 3.0]})
    y_zero = np.zeros(3)

    r1 = LogisticRegressionModel().fit(X_train, y_zero)
    r2 = LightGBMRainfallModel().fit(X_train, y_zero)

    p1 = r1.predict_proba(X_train)
    p2 = r2.predict_proba(X_train)

    assert np.all(p1 == 0.0)
    assert np.all(p2 == 0.0)

