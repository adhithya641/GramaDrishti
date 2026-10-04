"""
GramDrishti — Phase 7 Reliability, Confidence & Fallback Tests
================================================================
Test suite for Phase 7 reliability evaluator, freshness tracker,
fallback hierarchy, advisory gating engine, API service, and panchayat aggregation.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.reliability.evaluator import ReliabilityEvaluator, FreshnessEvaluator
from src.reliability.fallback import FallbackHandler
from src.reliability.panchayat_reliability import PanchayatReliabilityAggregator
from src.reliability.advisory_gating import AdvisoryGatingEngine
from src.reliability.api_service import ReliabilityAPIService


@pytest.fixture
def evaluator():
    return ReliabilityEvaluator("configs/reliability_config.yaml")


@pytest.fixture
def fallback_handler():
    return FallbackHandler()


@pytest.fixture
def gating_engine():
    return AdvisoryGatingEngine()


@pytest.fixture
def api_service():
    return ReliabilityAPIService("configs/reliability_config.yaml")


# Test 1: HIGH classification
def test_high_confidence_classification(evaluator):
    res = evaluator.evaluate_temperature(
        predicted_temp=30.0,
        interval_width=4.0,
        test_coverage=0.8770
    )
    assert res["confidence"] == "HIGH"
    assert len(res["reasons"]) == 0


# Test 2: MEDIUM classification
def test_medium_confidence_classification(evaluator):
    res = evaluator.evaluate_temperature(
        predicted_temp=30.0,
        interval_width=7.5,  # Exceeds max_interval_width 6.0°C
        test_coverage=0.8770
    )
    assert res["confidence"] == "MEDIUM"
    assert "INTERVAL_WIDTH_EXCEEDS_MAX" in res["reasons"]


# Test 3: LOW classification
def test_low_confidence_classification(evaluator):
    res = evaluator.evaluate_temperature(
        predicted_temp=-25.0,  # Below min_valid_value -10.0°C
        interval_width=4.0,
        test_coverage=0.8770
    )
    assert res["confidence"] == "LOW"
    assert "VALUE_OUTSIDE_VALID_RANGE" in res["reasons"]


# Test 4: NOT_EVALUABLE classification
def test_not_evaluable_classification(evaluator):
    res = evaluator.evaluate_rainfall_threshold(
        threshold_name="25mm",
        predicted_prob=None,
        train_events=0,
        calib_events=0,
        test_events=0
    )
    assert res["confidence"] == "NOT_EVALUABLE"
    assert "NO_POSITIVE_EVENTS_IN_TRAIN" in res["reasons"]
    assert "NO_POSITIVE_EVENTS_IN_CALIBRATION" in res["reasons"]
    assert "NO_POSITIVE_EVENTS_IN_TEST" in res["reasons"]


# Test 5: Humidity correctly becomes LOW using Phase 5 evidence (coverage 20.15% < 70%)
def test_humidity_becomes_low_on_phase5_evidence(evaluator):
    res = evaluator.evaluate_humidity(
        predicted_humidity=65.0,
        interval_width=27.61,
        test_coverage=0.2015,
        temporal_shift_detected=True
    )
    assert res["confidence"] == "LOW"
    assert "CQR_TEST_COVERAGE_BELOW_TARGET" in res["reasons"]
    assert "TEMPORAL_DISTRIBUTION_SHIFT_DETECTED" in res["reasons"]


# Test 6: Rainfall >= 10 mm becomes NOT_EVALUABLE due to 0 train/calib events
def test_rainfall_10mm_not_evaluable(evaluator):
    res = evaluator.evaluate_rainfall_threshold(
        threshold_name="10mm",
        predicted_prob=0.005,
        train_events=0,
        calib_events=0,
        test_events=6
    )
    assert res["confidence"] == "NOT_EVALUABLE"
    assert "INSUFFICIENT_TRAINING_EVENTS" in res["reasons"] or "NO_POSITIVE_EVENTS_IN_TRAIN" in res["reasons"]


# Test 7: Rainfall >= 25 mm becomes NOT_EVALUABLE
def test_rainfall_25mm_not_evaluable(evaluator):
    res = evaluator.evaluate_rainfall_threshold(
        threshold_name="25mm",
        predicted_prob=None,
        train_events=0,
        calib_events=0,
        test_events=0
    )
    assert res["confidence"] == "NOT_EVALUABLE"


# Test 8: Expired forecast blocks actionable advisory
def test_expired_forecast_blocks_advisory(gating_engine):
    res = gating_engine.evaluate_advisory_eligibility(
        variable="temperature",
        predicted_value=32.0,
        confidence="HIGH",
        freshness_status="EXPIRED",
        reasons=["FORECAST_EXPIRED"],
        base_advisory_text="Apply irrigation."
    )
    assert res["advisory_status"] == "BLOCKED"
    assert res["actionable"] is False
    assert "expired" in res["advisory_message"].lower()


# Test 9: Fresh forecast remains eligible
def test_fresh_forecast_remains_eligible(gating_engine):
    res = gating_engine.evaluate_advisory_eligibility(
        variable="temperature",
        predicted_value=32.0,
        confidence="HIGH",
        freshness_status="FRESH",
        reasons=[],
        base_advisory_text="Apply standard irrigation schedule."
    )
    assert res["advisory_status"] == "ACTIONABLE"
    assert res["actionable"] is True
    assert res["advisory_message"] == "Apply standard irrigation schedule."


# Test 10: Fallback activates when primary model fails reliability gate
def test_fallback_activates_when_primary_unreliable(fallback_handler):
    res = fallback_handler.select_temperature_fallback(
        primary_pred=35.0,
        confidence="LOW",
        b2_pred=32.5,
        b3_pred=32.8
    )
    assert res["fallback_used"] is True
    assert res["source"] == "BASELINE_B2"
    assert res["selected_value"] == 32.5


# Test 11: No fallback is falsely labeled as AI output
def test_no_fallback_falsely_labeled_as_ai(fallback_handler):
    # Temperature baseline fallback
    t_fb = fallback_handler.select_temperature_fallback(
        primary_pred=35.0,
        confidence="LOW",
        b2_pred=32.5
    )
    assert t_fb["source"] != "PRIMARY_MODEL"
    assert t_fb["fallback_used"] is True

    # Rainfall 25mm not evaluable
    rf_fb = fallback_handler.select_rainfall_fallback(
        threshold_name="25mm",
        primary_prob=None,
        confidence="NOT_EVALUABLE"
    )
    assert rf_fb["source"] == "NONE_NOT_EVALUABLE"
    assert rf_fb["selected_value"] is None


# Test 12: Panchayat aggregation preserves unresolved-grid flag
def test_panchayat_aggregation_preserves_subgrid_flag():
    df = pd.DataFrame([
        {
            "panchayat_id": "GP_FEW_CELLS",
            "timestamp": "2024-05-01 00:00:00",
            "lead_time": 24,
            "ml_temperature": 30.0,
            "ml_humidity": 65.0,
            "prob_1mm": 0.1,
            "prob_10mm": None,
            "prob_25mm": None
        },
        {
            "panchayat_id": "GP_FEW_CELLS",
            "timestamp": "2024-05-01 00:00:00",
            "lead_time": 24,
            "ml_temperature": 30.5,
            "ml_humidity": 66.0,
            "prob_1mm": 0.12,
            "prob_10mm": None,
            "prob_25mm": None
        }
    ])  # Only 2 grid cells (<3)

    aggregator = PanchayatReliabilityAggregator("configs/reliability_config.yaml")
    res_df = aggregator.aggregate_panchayat_reliability(df)
    assert len(res_df) == 1
    assert res_df.iloc[0]["aggregation_status"] == "SUBGRID_RANGE_UNRESOLVED"
    assert "SUBGRID_RANGE_UNRESOLVED" in res_df.iloc[0]["reliability_reasons"]


# Test 13: Reliability reasons are deterministic
def test_deterministic_reasons(evaluator):
    res1 = evaluator.evaluate_rainfall_threshold("25mm", None, 0, 0, 0)
    res2 = evaluator.evaluate_rainfall_threshold("25mm", None, 0, 0, 0)
    assert res1["reasons"] == res2["reasons"]


# Test 14: No NaN/invalid confidence values
def test_no_nan_confidence_values(api_service):
    res = api_service.get_panchayat_reliability("GP_TEST_01")
    rel = res["reliability"]
    assert rel["overall"] in ["HIGH", "MEDIUM", "LOW", "NOT_EVALUABLE", "EXPIRED", "UNAVAILABLE"]
    assert rel["temperature"] in ["HIGH", "MEDIUM", "LOW", "NOT_EVALUABLE"]
    assert rel["humidity"] in ["HIGH", "MEDIUM", "LOW", "NOT_EVALUABLE"]
    assert rel["rain_1mm"] in ["HIGH", "MEDIUM", "LOW", "NOT_EVALUABLE"]
    assert rel["rain_10mm"] == "NOT_EVALUABLE"
    assert rel["rain_25mm"] == "NOT_EVALUABLE"


# Test 15: Freshness evaluator handles aging and fresh statuses
def test_freshness_evaluator_statuses():
    f_eval = FreshnessEvaluator(fresh_max_hours=24.0, aging_max_hours=48.0)

    # Fresh forecast (12h age)
    res_fresh = f_eval.evaluate(
        timestamp="2024-05-01 00:00:00",
        reference_time="2024-05-01 12:00:00"
    )
    assert res_fresh["status"] == "FRESH"

    # Aging forecast (36h age)
    res_aging = f_eval.evaluate(
        timestamp="2024-05-01 00:00:00",
        reference_time="2024-05-02 12:00:00"
    )
    assert res_aging["status"] == "AGING"

    # Expired forecast (60h age)
    res_expired = f_eval.evaluate(
        timestamp="2024-05-01 00:00:00",
        reference_time="2024-05-03 12:00:00"
    )
    assert res_expired["status"] == "EXPIRED"
