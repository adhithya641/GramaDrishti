"""
GramDrishti — Phase 10A Live Weather Validation Layer
======================================================
Validates live weather observations from the ingestion layer.
Never blindly trusts API responses.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Physical bounds for Coimbatore / tropical India
TEMP_MIN_C = -5.0    # sanity minimum (won't occur in Coimbatore but physically grounded)
TEMP_MAX_C = 55.0    # extreme upper bound
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0
PRECIP_MIN = 0.0
WIND_MIN = 0.0
WIND_MAX_MS = 100.0  # extreme storm upper bound
PRESSURE_MIN_HPA = 850.0
PRESSURE_MAX_HPA = 1080.0


class ValidationError:
    def __init__(self, field: str, message: str, severity: str = "WARNING"):
        self.field = field
        self.message = message
        self.severity = severity  # "WARNING" | "ERROR"

    def __repr__(self):
        return f"[{self.severity}] {self.field}: {self.message}"


def validate_temperature(value: Optional[float]) -> List[ValidationError]:
    errors = []
    if value is None:
        errors.append(ValidationError("temperature_c", "Missing temperature", "ERROR"))
    elif not (TEMP_MIN_C <= value <= TEMP_MAX_C):
        errors.append(ValidationError(
            "temperature_c",
            f"Out of physical range: {value}°C (expected {TEMP_MIN_C}–{TEMP_MAX_C})",
            "ERROR"
        ))
    return errors


def validate_humidity(value: Optional[float]) -> List[ValidationError]:
    errors = []
    if value is None:
        errors.append(ValidationError("relative_humidity_pct", "Missing humidity", "WARNING"))
    elif not (HUMIDITY_MIN <= value <= HUMIDITY_MAX):
        errors.append(ValidationError(
            "relative_humidity_pct",
            f"Out of physical range: {value}% (expected 0–100)",
            "ERROR"
        ))
    return errors


def validate_precipitation(value: Optional[float]) -> List[ValidationError]:
    errors = []
    if value is None:
        return errors  # optional field
    if value < PRECIP_MIN:
        errors.append(ValidationError(
            "precipitation_mm",
            f"Negative precipitation: {value}mm",
            "ERROR"
        ))
    return errors


def validate_wind_speed(value: Optional[float]) -> List[ValidationError]:
    errors = []
    if value is None:
        return errors  # optional field
    if value < WIND_MIN or value > WIND_MAX_MS:
        errors.append(ValidationError(
            "wind_speed_ms",
            f"Out of physical range: {value} m/s (expected 0–{WIND_MAX_MS})",
            "WARNING"
        ))
    return errors


def validate_pressure(value: Optional[float]) -> List[ValidationError]:
    errors = []
    if value is None:
        return errors  # optional field
    if not (PRESSURE_MIN_HPA <= value <= PRESSURE_MAX_HPA):
        errors.append(ValidationError(
            "surface_pressure_hpa",
            f"Out of physical range: {value} hPa",
            "WARNING"
        ))
    return errors


def validate_timestamp(ts: Optional[str]) -> List[ValidationError]:
    errors = []
    if ts is None:
        errors.append(ValidationError("timestamp", "Missing timestamp", "ERROR"))
        return errors
    try:
        # Open-Meteo returns local ISO8601 without Z but with offset implied
        datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        errors.append(ValidationError(
            "timestamp",
            f"Cannot parse timestamp: {ts}",
            "ERROR"
        ))
    return errors


def validate_live_weather(data: Dict[str, Any]) -> Tuple[bool, List[ValidationError], Dict[str, Any]]:
    """
    Validate a parsed live weather observation.

    Returns:
        (is_valid, errors, summary)
        is_valid: True if no ERROR-level issues found
        errors: list of ValidationError instances
        summary: dict with field statuses
    """
    all_errors: List[ValidationError] = []

    all_errors.extend(validate_timestamp(data.get("timestamp")))
    all_errors.extend(validate_temperature(data.get("temperature_c")))
    all_errors.extend(validate_humidity(data.get("relative_humidity_pct")))
    all_errors.extend(validate_precipitation(data.get("precipitation_mm")))
    all_errors.extend(validate_wind_speed(data.get("wind_speed_ms")))
    all_errors.extend(validate_pressure(data.get("surface_pressure_hpa")))

    error_level = [e for e in all_errors if e.severity == "ERROR"]
    is_valid = len(error_level) == 0

    summary = {
        "valid": is_valid,
        "error_count": len(error_level),
        "warning_count": len([e for e in all_errors if e.severity == "WARNING"]),
        "errors": [str(e) for e in error_level],
        "warnings": [str(e) for e in all_errors if e.severity == "WARNING"],
        "data_age_seconds": data.get("data_age_seconds"),
        "freshness_status": _classify_freshness(data.get("data_age_seconds")),
    }

    return is_valid, all_errors, summary


def _classify_freshness(age_seconds: Optional[float]) -> str:
    if age_seconds is None:
        return "UNKNOWN"
    if age_seconds <= 900:
        return "FRESH"
    elif age_seconds <= 3600:
        return "AGING"
    elif age_seconds <= 10800:
        return "STALE"
    return "EXPIRED"


def get_mode_label(fetch_status: str, freshness: str) -> str:
    """
    Return a human-readable mode label based on fetch status and freshness.
    Must never label non-live data as live.
    """
    if fetch_status == "live":
        if freshness in ("FRESH", "AGING"):
            return "LIVE DATA"
        else:
            return "LIVE DATA — STALE"
    elif fetch_status == "cached":
        return "LIVE DATA — CACHED"
    else:
        return "HISTORICAL REPLAY"
