"""
GramDrishti — Forecast Loader & Review
=======================================
Loads Phase 1 historical coarse forecast data, preserves forecast issue time,
valid time, and lead time.

Data Provenance Note:
  DATA STATUS = STAND-IN (Open-Meteo Historical Forecast Archive).
  Must NOT be relabeled as operational IMD forecast data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict
import pandas as pd

logger = logging.getLogger("gramdrishti.matchups.forecast_loader")

DATA_STATUS_LABEL = "STAND-IN"


def load_forecasts(
    forecast_csv_path: str | Path,
) -> pd.DataFrame:
    """
    Load Phase 1 historical coarse forecast data.

    Parameters
    ----------
    forecast_csv_path : str | Path
        Path to Phase 1 historical forecast CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame with standardized forecast columns:
        forecast_issue_time, valid_time, lead_time_hours, latitude, longitude,
        forecast_temperature, forecast_humidity, forecast_rainfall, data_status
    """
    path = Path(forecast_csv_path)
    logger.info("Loading Phase 1 historical coarse forecasts from %s...", path.name)

    if not path.exists():
        raise FileNotFoundError(f"Forecast dataset not found: {path}")

    df = pd.read_csv(path)
    required = ["forecast_issue_time", "valid_time", "lead_time", "latitude", "longitude"]
    for col in required:
        if col not in df.columns:
            raise KeyError(f"Missing required field in forecast file: {col}")

    # Standardize datetime fields
    df["forecast_issue_time"] = pd.to_datetime(df["forecast_issue_time"], errors="coerce")
    df["valid_time"] = pd.to_datetime(df["valid_time"], errors="coerce")
    df = df.dropna(subset=["forecast_issue_time", "valid_time"]).copy()

    df["lead_time_hours"] = pd.to_numeric(df["lead_time"], errors="coerce").astype(int)

    # Standardize forecast variable names
    df["forecast_temperature"] = pd.to_numeric(df.get("temperature", df.get("forecast_temperature")), errors="coerce")
    df["forecast_humidity"] = pd.to_numeric(df.get("humidity", df.get("forecast_humidity")), errors="coerce")
    df["forecast_rainfall"] = pd.to_numeric(df.get("rainfall", df.get("forecast_rainfall")), errors="coerce").fillna(0.0)

    df["data_status"] = DATA_STATUS_LABEL

    logger.info("Loaded %d forecast records (%s status). Valid time range: %s to %s",
                len(df), DATA_STATUS_LABEL, str(df["valid_time"].min()), str(df["valid_time"].max()))

    return df
