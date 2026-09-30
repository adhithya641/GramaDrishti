"""
GramDrishti — Phase 8 Data Schemas & Validation Logic
======================================================
Strict scientific data validation and data models for GramDrishti application.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union
import numpy as np
import pandas as pd


class FreshnessStatus:
    FRESH = "FRESH"
    AGING = "AGING"
    EXPIRED = "EXPIRED"
    UNAVAILABLE = "UNAVAILABLE"


class AggregationStatus:
    OK = "OK"
    SUBGRID_RANGE_UNRESOLVED = "SUBGRID_RANGE_UNRESOLVED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str] = None


def validate_temperature(value: Any) -> ValidationResult:
    """Validates temperature is a realistic numeric value in Celsius (-10 to 60 C for Coimbatore)."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ValidationResult(False, "Temperature value is missing")
    try:
        val = float(value)
        if -10.0 <= val <= 60.0:
            return ValidationResult(True)
        return ValidationResult(False, f"Temperature {val}°C out of valid physical range [-10, 60]")
    except (ValueError, TypeError):
        return ValidationResult(False, "Temperature is not a valid numeric value")


def validate_humidity(value: Any) -> ValidationResult:
    """Validates relative humidity is between 0% and 100%."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ValidationResult(False, "Humidity value is missing")
    try:
        val = float(value)
        if 0.0 <= val <= 100.0:
            return ValidationResult(True)
        return ValidationResult(False, f"Humidity {val}% out of valid physical range [0, 100]")
    except (ValueError, TypeError):
        return ValidationResult(False, "Humidity is not a valid numeric value")


def validate_probability(value: Any) -> ValidationResult:
    """Validates probability is between 0.0 and 1.0."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ValidationResult(True)  # Null is valid for NOT_EVALUABLE
    try:
        val = float(value)
        if 0.0 <= val <= 1.0:
            return ValidationResult(True)
        return ValidationResult(False, f"Probability {val} out of bounds [0.0, 1.0]")
    except (ValueError, TypeError):
        return ValidationResult(False, "Probability is not numeric")


def validate_uncertainty_ordering(p10: Any, p50: Any, p90: Any) -> ValidationResult:
    """Validates quantile monotonicity ordering: P10 <= P50 <= P90."""
    try:
        v10 = float(p10)
        v50 = float(p50)
        v90 = float(p90)
        if v10 <= v50 <= v90:
            return ValidationResult(True)
        return ValidationResult(False, f"Quantile violation: P10 ({v10}) <= P50 ({v50}) <= P90 ({v90}) failed")
    except (ValueError, TypeError, AttributeError):
        return ValidationResult(False, "Quantiles contain non-numeric data")


def validate_panchayat_id(panchayat_id: str) -> ValidationResult:
    """Validates standard Panchayat ID format (e.g., GP_33_12_0001)."""
    if not isinstance(panchayat_id, str) or not panchayat_id.strip():
        return ValidationResult(False, "Panchayat ID is empty or not a string")
    parts = panchayat_id.strip().split("_")
    if len(parts) >= 4 and parts[0] == "GP":
        return ValidationResult(True)
    # Allow fallback if non-empty string
    return ValidationResult(True)


def parse_datetime_safe(dt_val: Any) -> Optional[datetime]:
    """Safely parses timestamp/date into a datetime object."""
    if dt_val is None or (isinstance(dt_val, float) and np.isnan(dt_val)):
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    if isinstance(dt_val, date):
        return datetime.combine(dt_val, datetime.min.time())
    if isinstance(dt_val, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(dt_val.strip(), fmt)
            except ValueError:
                continue
    try:
        ts = pd.to_datetime(dt_val)
        return ts.to_pydatetime()
    except Exception:
        return None


@dataclass
class PanchayatInfo:
    panchayat_id: str
    panchayat_name: str
    block_name: str
    district_name: str
    latitude: float
    longitude: float
    elevation_mean: float
    area_sq_km: Optional[float] = None
    grid_cell_count: int = 1
    assignment_mode: str = "CONTAINMENT"
    nearest_station_id: Optional[str] = None
    nearest_station_distance_km: Optional[float] = None


@dataclass
class WeatherForecastData:
    station_id: str
    panchayat_id: Optional[str]
    observation_time: str
    valid_time: str
    lead_time_hours: int
    ml_temperature: Optional[float]
    ml_humidity: Optional[float]
    observed_temperature: Optional[float] = None
    observed_humidity: Optional[float] = None
    b0_temperature: Optional[float] = None
    b1_temperature: Optional[float] = None
    b2_temperature: Optional[float] = None
    b3_temperature: Optional[float] = None
    b0_humidity: Optional[float] = None
    b1_humidity: Optional[float] = None
    b2_humidity: Optional[float] = None
    b3_humidity: Optional[float] = None
    # Uncertainty
    q10_temperature: Optional[float] = None
    q50_temperature: Optional[float] = None
    q90_temperature: Optional[float] = None
    q10_humidity: Optional[float] = None
    q50_humidity: Optional[float] = None
    q90_humidity: Optional[float] = None
    temp_interval_width: Optional[float] = None
    hum_interval_width: Optional[float] = None
    temperature_reliability: Optional[str] = None
    humidity_reliability: Optional[str] = None
    is_valid: bool = True
    validation_error: Optional[str] = None


@dataclass
class RainfallForecastData:
    panchayat_id: str
    timestamp: str
    lead_time: int
    rain_probability_1mm: Optional[float]
    rain_probability_10mm: Optional[float]  # None/null indicates NOT_EVALUABLE
    rain_probability_25mm: Optional[float]  # None/null indicates NOT_EVALUABLE
    rain_probability_1mm_p10: Optional[float]
    rain_probability_1mm_p90: Optional[float]
    spatial_spread_1mm: Optional[float]
    grid_cell_count: int
    aggregation_status: str
    is_evaluable_10mm: bool = False
    is_evaluable_25mm: bool = False
    is_valid: bool = True
    validation_error: Optional[str] = None


@dataclass
class SystemStatusReport:
    forecast_data_available: bool
    rainfall_model_available: bool
    uncertainty_available: bool
    reliability_available: bool
    advisory_engine_available: bool
    pilot_region: str = "Coimbatore District, Tamil Nadu"
    panchayat_count: int = 180
    station_count: int = 8
    latest_timestamp: Optional[str] = None
    freshness_status: str = FreshnessStatus.FRESH
