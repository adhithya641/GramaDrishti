"""
GramDrishti — Phase 7 API & Dashboard Service Interface
========================================================
Provides structured JSON responses for API endpoints and dashboard components:
  - GET /panchayat/{id}/reliability
  - GET /panchayat/{id}/forecast
  - GET /panchayat/{id}/advisory
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
from .evaluator import ReliabilityEvaluator, FreshnessEvaluator
from .fallback import FallbackHandler
from .advisory_gating import AdvisoryGatingEngine


class ReliabilityAPIService:
    """
    API Service handler for returning structured JSON formats required by Phase 7 specs.
    """

    def __init__(self, config_path: Optional[str] = "configs/reliability_config.yaml"):
        self.evaluator = ReliabilityEvaluator(config_path)
        self.fallback_handler = FallbackHandler()
        self.gating_engine = AdvisoryGatingEngine()

    def get_panchayat_reliability(
        self,
        panchayat_id: str,
        timestamp: str = "2024-05-01T00:00:00",
        lead_time: int = 24,
        temperature: float = 32.4,
        humidity: float = 68.5,
        prob_1mm: float = 0.112,
        prob_10mm: Optional[float] = None,
        prob_25mm: Optional[float] = None,
        grid_cell_count: int = 5,
        reference_time: Optional[str] = "2024-05-01T00:00:00"
    ) -> Dict[str, Any]:
        """
        Structured JSON response for GET /panchayat/{id}/reliability endpoint.
        """
        fresh_eval = self.evaluator.freshness_evaluator.evaluate(
            timestamp=timestamp,
            reference_time=reference_time,
            lead_time_hours=lead_time
        )

        temp_eval = self.evaluator.evaluate_temperature(temperature, interval_width=4.73)
        hum_eval = self.evaluator.evaluate_humidity(humidity, interval_width=27.61)
        r1_eval = self.evaluator.evaluate_rainfall_threshold("1mm", prob_1mm, train_events=15, calib_events=9, test_events=165, temporal_shift=True)
        r10_eval = self.evaluator.evaluate_rainfall_threshold("10mm", prob_10mm, train_events=0, calib_events=0, test_events=6)
        r25_eval = self.evaluator.evaluate_rainfall_threshold("25mm", prob_25mm, train_events=0, calib_events=0, test_events=0)

        overall_eval = self.evaluator.evaluate_overall_panchayat(
            temp_eval, hum_eval, r1_eval, r10_eval, r25_eval, fresh_eval, grid_cell_count=grid_cell_count
        )

        temp_fallback = self.fallback_handler.select_temperature_fallback(
            primary_pred=temperature,
            confidence=temp_eval["confidence"]
        )

        hum_fallback = self.fallback_handler.select_humidity_fallback(
            primary_pred=humidity,
            confidence=hum_eval["confidence"]
        )

        r10_fallback = self.fallback_handler.select_rainfall_fallback(
            threshold_name="10mm",
            primary_prob=prob_10mm,
            confidence=r10_eval["confidence"]
        )

        r25_fallback = self.fallback_handler.select_rainfall_fallback(
            threshold_name="25mm",
            primary_prob=prob_25mm,
            confidence=r25_eval["confidence"]
        )

        return {
            "panchayat_id": panchayat_id,
            "forecast": {
                "temperature": temperature,
                "humidity": humidity,
                "lead_time": lead_time,
                "timestamp": timestamp
            },
            "uncertainty": {
                "temperature_p10": round(temperature - 2.36, 2),
                "temperature_p50": temperature,
                "temperature_p90": round(temperature + 2.36, 2),
                "temperature_interval_width": 4.73,
                "humidity_p10": round(max(0.0, humidity - 13.8), 2),
                "humidity_p50": humidity,
                "humidity_p90": round(min(100.0, humidity + 13.8), 2),
                "humidity_interval_width": 27.61
            },
            "rainfall_probability": {
                "rain_1mm": prob_1mm,
                "rain_10mm": r10_fallback["selected_value"],
                "rain_25mm": r25_fallback["selected_value"]
            },
            "reliability": {
                "overall": overall_eval["overall"],
                "temperature": temp_eval["confidence"],
                "humidity": hum_eval["confidence"],
                "rain_1mm": r1_eval["confidence"],
                "rain_10mm": r10_eval["confidence"],
                "rain_25mm": r25_eval["confidence"]
            },
            "reasons": {
                "humidity": hum_eval["reasons"],
                "rain_10mm": r10_eval["reasons"],
                "rain_25mm": r25_eval["reasons"]
            },
            "freshness": fresh_eval,
            "fallback": {
                "temperature": temp_fallback,
                "humidity": hum_fallback,
                "rain_10mm": r10_fallback,
                "rain_25mm": r25_fallback
            },
            "panchayat_aggregation": {
                "grid_cell_count": grid_cell_count,
                "status": overall_eval["subgrid_status"]
            }
        }

    def get_panchayat_advisory(
        self,
        panchayat_id: str,
        variable: str = "humidity",
        base_advisory_text: str = "Apply light irrigation in early morning.",
        confidence: str = "LOW",
        freshness_status: str = "FRESH",
        reasons: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Structured JSON response for GET /panchayat/{id}/advisory endpoint.
        """
        if reasons is None:
            reasons = ["CQR_TEST_COVERAGE_BELOW_TARGET", "TEMPORAL_DISTRIBUTION_SHIFT_DETECTED"]

        gating_res = self.gating_engine.evaluate_advisory_eligibility(
            variable=variable,
            predicted_value=None,
            confidence=confidence,
            freshness_status=freshness_status,
            reasons=reasons,
            base_advisory_text=base_advisory_text
        )

        return {
            "panchayat_id": panchayat_id,
            "advisory": gating_res
        }
