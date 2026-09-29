"""
GramDrishti — Observation Loader & QC Review
==============================================
Loads Phase 1 ground station observations, reviews QC status flags, and formats
observation target variables.

QC Policy:
  - VALID: Primary target truth
  - SUSPICIOUS: Preserved and flagged (included with warnings)
  - INVALID: Excluded from baseline evaluation truth
  - MISSING: Excluded
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple
import pandas as pd

logger = logging.getLogger("gramdrishti.matchups.observation_loader")


def load_observations(
    obs_csv_path: str | Path,
) -> pd.DataFrame:
    """
    Load Phase 1 station observations and standardize target columns.

    Parameters
    ----------
    obs_csv_path : str | Path
        Path to Phase 1 processed or raw observation CSV file.

    Returns
    -------
    pd.DataFrame
        DataFrame with standardized observation columns:
        station_id, timestamp, latitude, longitude, station_elevation,
        observed_temperature, observed_humidity, observed_rainfall, qc_status
    """
    path = Path(obs_csv_path)
    logger.info("Loading Phase 1 weather station observations from %s...", path.name)

    if not path.exists():
        raise FileNotFoundError(f"Observation dataset not found: {path}")

    df = pd.read_csv(path)
    required = ["station_id", "timestamp", "latitude", "longitude"]
    for col in required:
        if col not in df.columns:
            raise KeyError(f"Missing required field in observation file: {col}")

    # Standardize timestamp to pandas datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).copy()

    # Standardize target variable names
    df["observed_temperature"] = pd.to_numeric(df.get("temperature", df.get("observed_temperature")), errors="coerce")
    df["observed_humidity"] = pd.to_numeric(df.get("humidity", df.get("observed_humidity")), errors="coerce")
    df["observed_rainfall"] = pd.to_numeric(df.get("rainfall", df.get("observed_rainfall")), errors="coerce").fillna(0.0)
    df["station_elevation"] = pd.to_numeric(df.get("station_elevation"), errors="coerce").fillna(350.0)

    # Consolidate overall QC status
    if "qc_status" not in df.columns:
        qc_cols = [c for c in df.columns if c.startswith("qc_")]
        if qc_cols:
            # If any column is SUSPICIOUS/INVALID, reflect in overall qc_status
            statuses = []
            for idx, row in df.iterrows():
                row_qcs = [str(row[c]) for c in qc_cols]
                if "INVALID" in row_qcs:
                    statuses.append("INVALID")
                elif "SUSPICIOUS" in row_qcs:
                    statuses.append("SUSPICIOUS")
                else:
                    statuses.append("VALID")
            df["qc_status"] = statuses
        else:
            df["qc_status"] = "VALID"

    # QC Breakdown Summary
    qc_counts = df["qc_status"].value_counts().to_dict()
    logger.info("Loaded %d observation records across %d stations. QC Breakdown: %s",
                len(df), df["station_id"].nunique(), qc_counts)

    return df
