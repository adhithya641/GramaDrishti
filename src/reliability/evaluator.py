"""
GramDrishti — Phase 7 Reliability & Confidence Evaluator
=========================================================
Rule-based evaluation system for forecast reliability, uncertainty quality,
rainfall data sufficiency, temporal distribution shift, and forecast freshness.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timezone
import yaml
import json
import os
import pandas as pd
import numpy as np


class FreshnessEvaluator:
    """Evaluates forecast freshness and validity metadata."""

    def __init__(self, fresh_max_hours: float = 24.0, aging_max_hours: float = 48.0):
        self.fresh_max_hours = fresh_max_hours
        self.aging_max_hours = aging_max_hours

    def evaluate(
        self,
        timestamp: Union[str, datetime],
        reference_time: Optional[Union[str, datetime]] = None,
        lead_time_hours: int = 0
    ) -> Dict[str, Any]:
        """
        Evaluate freshness of a forecast timestamp.
        """
        if timestamp is None:
            return {
                "status": "UNAVAILABLE",
                "data_age_hours": None,
                "generated_at": None,
                "valid_time": None,
                "valid_until": None,
                "reasons": ["FORECAST_UNAVAILABLE"]
            }

        try:
            if isinstance(timestamp, str):
                dt_valid = pd.to_datetime(timestamp)
            else:
                dt_valid = pd.to_datetime(timestamp)

            if reference_time is None:
                # Default reference time for verification/testing
                dt_ref = pd.to_datetime("2024-05-01 00:00:00")
            else:
                dt_ref = pd.to_datetime(reference_time)

            # Age in hours relative to valid time / reference time
            data_age_hours = float((dt_ref - dt_valid).total_seconds() / 3600.0)
            if data_age_hours < 0:
                data_age_hours = 0.0

            valid_until = dt_valid + pd.Timedelta(hours=self.aging_max_hours)

            reasons = []
            if data_age_hours <= self.fresh_max_hours:
                status = "FRESH"
            elif data_age_hours <= self.aging_max_hours:
                status = "AGING"
                reasons.append("FORECAST_AGING")
            else:
                status = "EXPIRED"
                reasons.append("FORECAST_EXPIRED")

            return {
                "status": status,
                "data_age_hours": round(data_age_hours, 2),
                "generated_at": (dt_valid - pd.Timedelta(hours=lead_time_hours)).isoformat(),
                "valid_time": dt_valid.isoformat(),
                "valid_until": valid_until.isoformat(),
                "reasons": reasons
            }
        except Exception:
            return {
                "status": "UNAVAILABLE",
                "data_age_hours": None,
                "generated_at": None,
                "valid_time": str(timestamp),
                "valid_until": None,
                "reasons": ["FORECAST_UNAVAILABLE"]
            }


class ReliabilityEvaluator:
    """
    Evidence-based rule engine for classifying prediction reliability into:
    HIGH, MEDIUM, LOW, NOT_EVALUABLE.
    """

    def __init__(self, config_path: Optional[str] = "configs/reliability_config.yaml"):
        self.config = self._load_config(config_path)
        self.freshness_evaluator = FreshnessEvaluator(
            fresh_max_hours=self.config.get("reliability", {}).get("freshness", {}).get("fresh_max_hours", 24.0),
            aging_max_hours=self.config.get("reliability", {}).get("freshness", {}).get("aging_max_hours", 48.0)
        )

    def _load_config(self, path: Optional[str]) -> Dict[str, Any]:
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {
            "reliability": {
                "temperature": {"target_coverage": 0.80, "min_coverage": 0.70, "max_interval_width": 6.0},
                "humidity": {"target_coverage": 0.80, "min_coverage": 0.70, "max_interval_width": 35.0},
                "rainfall": {
                    "thresholds": {
                        "1mm": {"min_training_events": 10, "min_calibration_events": 5},
                        "10mm": {"min_training_events": 10, "min_calibration_events": 5},
                        "25mm": {"min_training_events": 10, "min_calibration_events": 5}
                    }
                },
                "freshness": {"fresh_max_hours": 24.0, "aging_max_hours": 48.0}
            }
        }

    def evaluate_temperature(
        self,
        predicted_temp: float,
        interval_width: Optional[float] = None,
        test_coverage: float = 0.8770,
        mae: float = 1.2225
    ) -> Dict[str, Any]:
        """Evaluate Temperature prediction reliability."""
        reasons = []
        cfg = self.config.get("reliability", {}).get("temperature", {})
        min_cov = cfg.get("min_coverage", 0.70)
        max_w = cfg.get("max_interval_width", 6.0)

        confidence = "HIGH"

        if test_coverage < min_cov:
            confidence = "LOW"
            reasons.append("CQR_TEST_COVERAGE_BELOW_TARGET")

        if interval_width is not None and interval_width > max_w:
            if confidence == "HIGH":
                confidence = "MEDIUM"
            reasons.append("INTERVAL_WIDTH_EXCEEDS_MAX")

        if predicted_temp < cfg.get("min_valid_value", -10.0) or predicted_temp > cfg.get("max_valid_value", 55.0):
            confidence = "LOW"
            reasons.append("VALUE_OUTSIDE_VALID_RANGE")

        return {
            "variable": "temperature",
            "confidence": confidence,
            "reasons": reasons,
            "metrics": {
                "predicted_value": predicted_temp,
                "test_coverage": test_coverage,
                "interval_width": interval_width,
                "test_mae": mae
            }
        }

    def evaluate_humidity(
        self,
        predicted_humidity: float,
        interval_width: Optional[float] = None,
        test_coverage: float = 0.2015,
        mae: float = 19.4556,
        temporal_shift_detected: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate Humidity prediction reliability.
        Note: Humidity test coverage in Phase 5 is 20.15% (well below 70%),
        so humidity MUST downgrade to LOW with explicit reasons.
        """
        reasons = []
        cfg = self.config.get("reliability", {}).get("humidity", {})
        min_cov = cfg.get("min_coverage", 0.70)
        max_w = cfg.get("max_interval_width", 35.0)

        # Humidity has severe undercoverage in test split (20.15% < 70%)
        if test_coverage < min_cov:
            confidence = "LOW"
            reasons.append("CQR_TEST_COVERAGE_BELOW_TARGET")
        else:
            confidence = "HIGH"

        if temporal_shift_detected:
            reasons.append("TEMPORAL_DISTRIBUTION_SHIFT_DETECTED")
            if confidence == "HIGH":
                confidence = "MEDIUM"

        if interval_width is not None and interval_width > max_w:
            reasons.append("INTERVAL_WIDTH_EXCEEDS_MAX")
            confidence = "LOW"

        if predicted_humidity < cfg.get("min_valid_value", 0.0) or predicted_humidity > cfg.get("max_valid_value", 100.0):
            confidence = "LOW"
            reasons.append("VALUE_OUTSIDE_VALID_RANGE")

        return {
            "variable": "humidity",
            "confidence": confidence,
            "reasons": reasons,
            "metrics": {
                "predicted_value": predicted_humidity,
                "test_coverage": test_coverage,
                "interval_width": interval_width,
                "test_mae": mae
            }
        }

    def evaluate_rainfall_threshold(
        self,
        threshold_name: str,
        predicted_prob: Optional[float],
        train_events: int,
        calib_events: int,
        test_events: int,
        temporal_shift: bool = False
    ) -> Dict[str, Any]:
        """
        Evaluate Rainfall threshold probability reliability based on data sufficiency.
        """
        reasons = []
        cfg_rf = self.config.get("reliability", {}).get("rainfall", {}).get("thresholds", {}).get(threshold_name, {})
        min_train = cfg_rf.get("min_training_events", 10)
        min_calib = cfg_rf.get("min_calibration_events", 5)

        # Factual event status
        if train_events == 0:
            reasons.append("NO_POSITIVE_EVENTS_IN_TRAIN")
        elif train_events < min_train:
            reasons.append("INSUFFICIENT_TRAINING_EVENTS")

        if calib_events == 0:
            reasons.append("NO_POSITIVE_EVENTS_IN_CALIBRATION")
        elif calib_events < min_calib:
            reasons.append("INSUFFICIENT_CALIBRATION_EVENTS")

        if test_events == 0:
            reasons.append("NO_POSITIVE_EVENTS_IN_TEST")

        if temporal_shift:
            reasons.append("TEMPORAL_DISTRIBUTION_SHIFT_DETECTED")

        # Classification decision rules
        if train_events < min_train or calib_events < min_calib:
            confidence = "NOT_EVALUABLE"
        elif temporal_shift:
            confidence = "MEDIUM"
        else:
            confidence = "HIGH"

        return {
            "threshold": threshold_name,
            "confidence": confidence,
            "reasons": sorted(list(set(reasons))),
            "metrics": {
                "predicted_probability": predicted_prob,
                "train_events": train_events,
                "calib_events": calib_events,
                "test_events": test_events
            }
        }

    def evaluate_overall_panchayat(
        self,
        temp_eval: Dict[str, Any],
        hum_eval: Dict[str, Any],
        rf_1mm_eval: Dict[str, Any],
        rf_10mm_eval: Dict[str, Any],
        rf_25mm_eval: Dict[str, Any],
        freshness_eval: Dict[str, Any],
        grid_cell_count: int = 5
    ) -> Dict[str, Any]:
        """
        Aggregate variable evaluations into an overall panchayat reliability record.
        """
        all_reasons = []
        for eval_dict in [temp_eval, hum_eval, rf_1mm_eval, rf_10mm_eval, rf_25mm_eval, freshness_eval]:
            all_reasons.extend(eval_dict.get("reasons", []))

        subgrid_status = "OK"
        if grid_cell_count < self.config.get("reliability", {}).get("panchayat", {}).get("min_grid_cells", 3):
            subgrid_status = "SUBGRID_RANGE_UNRESOLVED"
            all_reasons.append("SUBGRID_RANGE_UNRESOLVED")

        # Overall confidence logic
        conf_levels = [temp_eval["confidence"], hum_eval["confidence"], rf_1mm_eval["confidence"]]
        if freshness_eval["status"] == "EXPIRED":
            overall_conf = "EXPIRED"
        elif freshness_eval["status"] == "UNAVAILABLE":
            overall_conf = "UNAVAILABLE"
        elif "LOW" in conf_levels:
            overall_conf = "LOW"
        elif "MEDIUM" in conf_levels:
            overall_conf = "MEDIUM"
        else:
            overall_conf = "HIGH"

        return {
            "overall": overall_conf,
            "temperature": temp_eval["confidence"],
            "humidity": hum_eval["confidence"],
            "rain_1mm": rf_1mm_eval["confidence"],
            "rain_10mm": rf_10mm_eval["confidence"],
            "rain_25mm": rf_25mm_eval["confidence"],
            "freshness_status": freshness_eval["status"],
            "subgrid_status": subgrid_status,
            "grid_cell_count": grid_cell_count,
            "reasons": sorted(list(set(all_reasons)))
        }
