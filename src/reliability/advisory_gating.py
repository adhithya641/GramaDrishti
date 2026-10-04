"""
GramDrishti — Phase 7 Advisory Gating Engine
=============================================
Controls advisory generation based on forecast confidence, reliability reasons, and freshness.
Ensures honest uncertainty over false precision.
"""

from typing import Dict, Any, List, Optional


class AdvisoryGatingEngine:
    """
    Gating mechanism for crop advisories.
    Blocks actionable advisories when confidence is NOT_EVALUABLE or forecast is EXPIRED.
    """

    def __init__(self):
        pass

    def evaluate_advisory_eligibility(
        self,
        variable: str,
        predicted_value: Optional[float],
        confidence: str,
        freshness_status: str,
        reasons: List[str],
        base_advisory_text: str
    ) -> Dict[str, Any]:
        """
        Evaluate whether a weather condition is eligible for an actionable crop advisory.
        """
        # Block 1: Expired forecast
        if freshness_status in ["EXPIRED", "UNAVAILABLE"]:
            return {
                "advisory_status": "BLOCKED",
                "actionable": False,
                "variable": variable,
                "confidence": confidence,
                "freshness_status": freshness_status,
                "advisory_message": "Forecast is expired or unavailable. Actionable advisory cannot be generated.",
                "user_notice": "Forecast expired/unavailable."
            }

        # Block 2: Not evaluable condition (e.g. 10mm or 25mm rain)
        if confidence == "NOT_EVALUABLE":
            return {
                "advisory_status": "BLOCKED",
                "actionable": False,
                "variable": variable,
                "confidence": confidence,
                "freshness_status": freshness_status,
                "advisory_message": "Insufficient validated evidence for this condition at this location/time.",
                "user_notice": "Insufficient validated evidence for this condition at this location/time."
            }

        # Block 3: Low confidence condition (e.g. humidity undercoverage)
        if confidence == "LOW":
            caution_reasons = ", ".join(reasons) if reasons else "uncertain model evidence"
            return {
                "advisory_status": "CAUTIONARY",
                "actionable": True,
                "variable": variable,
                "confidence": confidence,
                "freshness_status": freshness_status,
                "advisory_message": f"CAUTION ({caution_reasons}): {base_advisory_text}",
                "user_notice": f"Cautionary message shown due to low reliability ({confidence})."
            }

        # Actionable condition (HIGH or MEDIUM confidence)
        return {
            "advisory_status": "ACTIONABLE",
            "actionable": True,
            "variable": variable,
            "confidence": confidence,
            "freshness_status": freshness_status,
            "advisory_message": base_advisory_text,
            "user_notice": "Actionable crop advisory."
        }
