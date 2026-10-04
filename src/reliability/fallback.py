"""
GramDrishti — Phase 7 Fallback Hierarchy Handler
=================================================
Selects valid fallback predictions when primary models are unreliable or unavailable.
Prevents false claims of AI superiority and prohibits false probability fabrication.
"""

from typing import Dict, Any, Optional, Union
import numpy as np
import pandas as pd


class FallbackHandler:
    """
    Implements evidence-based fallback logic.
    Hierarchy:
      Primary ML Model -> Best Validated Baseline (B2/B3) -> Coarse Forecast -> Unavailable.
    """

    def __init__(self):
        pass

    def select_temperature_fallback(
        self,
        primary_pred: float,
        confidence: str,
        b2_pred: Optional[float] = None,
        b3_pred: Optional[float] = None,
        district_coarse_pred: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Select temperature fallback if primary ML model is expired or unreliable.
        """
        if confidence in ["HIGH", "MEDIUM"]:
            return {
                "selected_value": primary_pred,
                "fallback_used": False,
                "source": "PRIMARY_MODEL",
                "reason": "Primary LightGBM residual model passed reliability gate."
            }

        # If primary ML model is LOW/EXPIRED/UNAVAILABLE
        if b2_pred is not None and not np.isnan(b2_pred):
            return {
                "selected_value": b2_pred,
                "fallback_used": True,
                "source": "BASELINE_B2",
                "reason": f"Primary model confidence was {confidence}. Fallback to B2 physical forecast."
            }
        elif b3_pred is not None and not np.isnan(b3_pred):
            return {
                "selected_value": b3_pred,
                "fallback_used": True,
                "source": "BASELINE_B3",
                "reason": f"Primary model confidence was {confidence}. Fallback to B3 linear regression."
            }
        elif district_coarse_pred is not None and not np.isnan(district_coarse_pred):
            return {
                "selected_value": district_coarse_pred,
                "fallback_used": True,
                "source": "COARSE_FORECAST",
                "reason": f"Primary model confidence was {confidence}. Fallback to coarse district average."
            }
        else:
            return {
                "selected_value": None,
                "fallback_used": True,
                "source": "UNAVAILABLE",
                "reason": "Primary prediction failed reliability gate and no validated baseline was available."
            }

    def select_humidity_fallback(
        self,
        primary_pred: float,
        confidence: str,
        b2_pred: Optional[float] = None,
        b3_pred: Optional[float] = None,
        district_coarse_pred: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Select humidity fallback if primary model is low reliability or expired.
        """
        if confidence in ["HIGH", "MEDIUM"]:
            return {
                "selected_value": primary_pred,
                "fallback_used": False,
                "source": "PRIMARY_MODEL",
                "reason": "Primary LightGBM model passed reliability gate."
            }

        # When primary model is LOW (which humidity is by default in test split due to 20.15% coverage):
        # Allow fallback to B2 baseline or flag transparently as LOW primary prediction
        if b2_pred is not None and not np.isnan(b2_pred):
            return {
                "selected_value": b2_pred,
                "fallback_used": True,
                "source": "BASELINE_B2",
                "reason": "Primary humidity model flagged as LOW reliability (coverage shift). Fallback to B2."
            }
        elif b3_pred is not None and not np.isnan(b3_pred):
            return {
                "selected_value": b3_pred,
                "fallback_used": True,
                "source": "BASELINE_B3",
                "reason": "Primary humidity model flagged as LOW reliability. Fallback to B3."
            }
        elif district_coarse_pred is not None and not np.isnan(district_coarse_pred):
            return {
                "selected_value": district_coarse_pred,
                "fallback_used": True,
                "source": "COARSE_FORECAST",
                "reason": "Fallback to coarse district average humidity."
            }
        else:
            # If no baseline provided, return primary prediction marked with fallback_used=False but flagged as LOW
            return {
                "selected_value": primary_pred,
                "fallback_used": False,
                "source": "PRIMARY_MODEL_LOW_RELIABILITY",
                "reason": "Primary model used with caution; no alternative baseline provided."
            }

    def select_rainfall_fallback(
        self,
        threshold_name: str,
        primary_prob: Optional[float],
        confidence: str
    ) -> Dict[str, Any]:
        """
        Select rainfall fallback.
        CRITICAL RULE: For unevaluable thresholds (10mm, 25mm), do NOT fabricate a fallback probability.
        """
        if confidence == "NOT_EVALUABLE":
            return {
                "selected_value": None,
                "fallback_used": False,
                "source": "NONE_NOT_EVALUABLE",
                "reason": f"Rainfall threshold {threshold_name} has insufficient training/calib events. No probability fabricated."
            }

        if confidence in ["HIGH", "MEDIUM"]:
            return {
                "selected_value": primary_prob,
                "fallback_used": False,
                "source": "PRIMARY_MODEL",
                "reason": f"Primary rainfall model for {threshold_name} passed reliability gate."
            }

        # If LOW confidence (e.g. 1mm under temporal shift)
        return {
            "selected_value": primary_prob,
            "fallback_used": False,
            "source": "PRIMARY_MODEL_CAUTION",
            "reason": f"Primary rainfall prediction for {threshold_name} shown with caution."
        }
