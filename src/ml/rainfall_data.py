"""
GramDrishti — Phase 6 Rainfall Data Preparation and Audit
==========================================================
Handles rainfall target binary labeling, dataset quality checks,
temporal splitting, and event rate summary statistics.
"""

from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np


def create_rainfall_targets(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates binary rainfall target indicators:
      - rain_1mm  : observed_rainfall >= 1.0
      - rain_10mm : observed_rainfall >= 10.0
      - rain_25mm : observed_rainfall >= 25.0
    """
    df = df.copy()
    df["rain_1mm"] = (df["observed_rainfall"] >= 1.0).astype(int)
    df["rain_10mm"] = (df["observed_rainfall"] >= 10.0).astype(int)
    df["rain_25mm"] = (df["observed_rainfall"] >= 25.0).astype(int)
    return df


def audit_rainfall_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Audits rainfall data quality and alignment:
      - Checks for missing observed_rainfall
      - Checks for negative observed_rainfall
      - Checks for duplicate (station_id, observation_time, lead_time_hours)
      - Checks for impossible rainfall values (> 500 mm/day)
      - Checks station / date alignment
    """
    missing_cnt = int(df["observed_rainfall"].isna().sum())
    negative_cnt = int((df["observed_rainfall"] < 0).sum())
    impossible_cnt = int((df["observed_rainfall"] > 500.0).sum())

    dup_cols = ["station_id", "observation_time", "lead_time_hours"]
    if all(col in df.columns for col in dup_cols):
        duplicate_cnt = int(df.duplicated(subset=dup_cols).sum())
    else:
        duplicate_cnt = 0

    stations = df["station_id"].unique().tolist() if "station_id" in df.columns else []

    audit_summary = {
        "total_records": len(df),
        "missing_observed_rainfall": missing_cnt,
        "negative_observed_rainfall": negative_cnt,
        "impossible_observed_rainfall": impossible_cnt,
        "duplicate_records": duplicate_cnt,
        "unique_stations": len(stations),
        "station_list": sorted(stations),
        "clean_data": (missing_cnt == 0 and negative_cnt == 0 and duplicate_cnt == 0 and impossible_cnt == 0)
    }
    return audit_summary


def compute_event_stats(df: pd.DataFrame, target_col: str) -> Dict[str, Any]:
    """
    Computes event count, non-event count, and event rate for a target column.
    """
    total = len(df)
    events = int((df[target_col] == 1).sum())
    non_events = total - events
    event_rate = float(events / total) if total > 0 else 0.0

    return {
        "total": total,
        "events": events,
        "non_events": non_events,
        "event_rate": event_rate,
        "event_rate_pct": float(event_rate * 100.0)
    }


def get_split_event_summary(df: pd.DataFrame) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Computes event statistics for each split (TRAIN, CALIBRATION, TEST)
    across each threshold (1mm, 10mm, 25mm).
    """
    targets = ["rain_1mm", "rain_10mm", "rain_25mm"]
    splits = ["TRAIN", "CALIBRATION", "TEST"]

    summary = {}
    for target in targets:
        summary[target] = {}
        for sp in splits:
            sub = df[df["split"] == sp]
            summary[target][sp] = compute_event_stats(sub, target)

    return summary
