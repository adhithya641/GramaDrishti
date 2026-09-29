"""
GramDrishti — Phase 6 Panchayat Aggregator
===========================================
Generates grid-level rainfall probability predictions across all 10,530 1-km grid cells
and aggregates them to the 180 Gram Panchayats in Coimbatore District.
"""

from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd


def aggregate_grid_to_panchayats(
    grid_predictions_df: pd.DataFrame,
    panchayat_meta_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Aggregates 1-km grid-level predictions to Panchayat-level outputs.

    Required columns in grid_predictions_df:
      - panchayat_id
      - observation_time (or timestamp)
      - lead_time_hours (or lead_time)
      - prob_1mm, prob_10mm, prob_25mm

    Returns DataFrame adhering to Phase 6 Panchayat Output Schema:
      panchayat_id, timestamp, lead_time,
      rain_probability_1mm, rain_probability_10mm, rain_probability_25mm,
      rain_probability_1mm_p10, rain_probability_1mm_p90,
      rain_probability_10mm_p10, rain_probability_10mm_p90,
      rain_probability_25mm_p10, rain_probability_25mm_p90,
      spatial_spread_1mm, spatial_spread_10mm, spatial_spread_25mm,
      grid_cell_count, aggregation_status
    """
    df = grid_predictions_df.copy()

    # Standardize column names
    time_col = "timestamp" if "timestamp" in df.columns else "observation_time"
    lead_col = "lead_time" if "lead_time" in df.columns else "lead_time_hours"

    df["timestamp"] = df[time_col]
    df["lead_time"] = df[lead_col]

    grouped_records = []

    # Group by panchayat_id, timestamp, lead_time
    group_cols = ["panchayat_id", "timestamp", "lead_time"]

    for (gp_id, ts, lt), sub_df in df.groupby(group_cols, observed=True):
        cell_cnt = len(sub_df)
        status = "SUBGRID_RANGE_UNRESOLVED" if cell_cnt < 3 else "OK"

        p1_vals = sub_df["prob_1mm"].values
        p10_vals = sub_df["prob_10mm"].values
        p25_vals = sub_df["prob_25mm"].values

        # 1mm stats
        p1_mean = float(np.mean(p1_vals))
        p1_p10 = float(np.percentile(p1_vals, 10))
        p1_p90 = float(np.percentile(p1_vals, 90))
        p1_spread = float(np.std(p1_vals, ddof=1)) if cell_cnt > 1 else 0.0

        # 10mm stats
        p10_mean = float(np.mean(p10_vals))
        p10_p10 = float(np.percentile(p10_vals, 10))
        p10_p90 = float(np.percentile(p10_vals, 90))
        p10_spread = float(np.std(p10_vals, ddof=1)) if cell_cnt > 1 else 0.0

        # 25mm stats
        p25_mean = float(np.mean(p25_vals))
        p25_p10 = float(np.percentile(p25_vals, 10))
        p25_p90 = float(np.percentile(p25_vals, 90))
        p25_spread = float(np.std(p25_vals, ddof=1)) if cell_cnt > 1 else 0.0

        grouped_records.append({
            "panchayat_id": gp_id,
            "timestamp": str(ts),
            "lead_time": int(lt),
            "rain_probability_1mm": p1_mean,
            "rain_probability_10mm": p10_mean,
            "rain_probability_25mm": p25_mean,
            "rain_probability_1mm_p10": p1_p10,
            "rain_probability_1mm_p90": p1_p90,
            "rain_probability_10mm_p10": p10_p10,
            "rain_probability_10mm_p90": p10_p90,
            "rain_probability_25mm_p10": p25_p10,
            "rain_probability_25mm_p90": p25_p90,
            "spatial_spread_1mm": p1_spread,
            "spatial_spread_10mm": p10_spread,
            "spatial_spread_25mm": p25_spread,
            "grid_cell_count": cell_cnt,
            "aggregation_status": status
        })

    panchayat_df = pd.DataFrame(grouped_records)
    return panchayat_df


def build_full_grid_features(
    geospatial_master: pd.DataFrame,
    forecasts_df: pd.DataFrame,
    forecast_mapping: pd.DataFrame,
    test_timestamps: List[str]
) -> pd.DataFrame:
    """
    Constructs full 1-km grid features across specified test timestamps and lead times
    by joining parent forecasts with geospatial grid features.
    """
    # Create lat/lon -> FC_GRID mapping
    pairs = forecasts_df[["latitude", "longitude"]].drop_duplicates().sort_values(by=["latitude", "longitude"]).reset_index(drop=True)
    pairs["forecast_parent_id"] = [f"FC_GRID_{i+1:02d}" for i in range(len(pairs))]

    fc_merged = forecasts_df.merge(pairs, on=["latitude", "longitude"], how="left")
    fc_merged["observation_time"] = pd.to_datetime(fc_merged["valid_time"]).dt.strftime("%Y-%m-%d")

    # Filter to test timestamps
    fc_test = fc_merged[fc_merged["observation_time"].isin(test_timestamps)].copy()

    # Rename forecast weather columns to match training features
    fc_test = fc_test.rename(columns={
        "temperature": "forecast_temperature",
        "humidity": "forecast_humidity",
        "rainfall": "forecast_rainfall",
        "lead_time": "lead_time_hours"
    })

    # Join with full 10,530 grid cells on forecast_parent_id
    full_grid_df = geospatial_master.merge(
        fc_test[["forecast_parent_id", "observation_time", "lead_time_hours",
                 "forecast_temperature", "forecast_humidity", "forecast_rainfall"]],
        on="forecast_parent_id",
        how="inner"
    )

    # Derive temporal features
    times = pd.to_datetime(full_grid_df["observation_time"])
    day_of_year = times.dt.dayofyear

    full_grid_df["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    full_grid_df["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    full_grid_df["month"] = times.dt.month

    return full_grid_df
