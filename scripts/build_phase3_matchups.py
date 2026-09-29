"""
GramDrishti — Phase 3 Weather Matchup & Baseline Forecasting Pipeline
========================================================================
Reproducible entry point for building the historical weather matchup dataset
and evaluating the baseline forecasting ladder (B0, B1, B2, B3).

Execution Steps:
  1. Load Phase 1 station observations and review QC flags
  2. Load Phase 1 historical forecasts (status = STAND-IN)
  3. Load Phase 2 master geospatial grid features
  4. Perform spatial & temporal matching and assign chronological splits
  5. Compute B0 Baseline (Coarse forecast)
  6. Compute B1 Baseline (Bilinear interpolation)
  7. Compute B2 Baseline (Elevation lapse-rate correction)
  8. Compute B3 Baseline (Quantile mapping fitted on TRAIN split)
  9. Compute target residuals for future Phase 4 ML
 10. Execute Quality Assurance Checks A through Q
 11. Calculate MAE, RMSE, Bias for B0, B1, B2, B3 across splits
 12. Save processed matchup datasets under data/processed/matchups/
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.matchups.observation_loader import load_observations
from src.matchups.forecast_loader import load_forecasts
from src.matchups.spatial_temporal_matcher import match_observations_and_forecasts
from src.matchups.baselines import (
    compute_b0_coarse,
    compute_b1_bilinear,
    compute_b2_lapse_rate,
    compute_b3_quantile_mapping,
    compute_residuals,
)
from src.matchups.validate_matchups import MatchupValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gramdrishti.phase3_build")


def calculate_metrics(df: pd.DataFrame, pred_col: str, target_col: str) -> Dict[str, float]:
    """Calculate MAE, RMSE, and Bias (Mean Error) between prediction and target."""
    valid_mask = df[pred_col].notna() & df[target_col].notna()
    sub = df[valid_mask]
    if sub.empty:
        return {"mae": np.nan, "rmse": np.nan, "bias": np.nan}

    errors = sub[pred_col] - sub[target_col]
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    bias = float(np.mean(errors))

    return {
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "bias": round(bias, 3),
    }


def main():
    logger.info("=========================================================")
    logger.info(" GramDrishti — Phase 3 Weather Matchup & Baselines Build ")
    logger.info("=========================================================")

    raw_dir = PROJECT_ROOT / "data" / "raw"
    proc_dir = PROJECT_ROOT / "data" / "processed"
    matchups_dir = proc_dir / "matchups"
    meta_dir = PROJECT_ROOT / "data" / "metadata"
    config_path = PROJECT_ROOT / "configs" / "baselines.yaml"

    matchups_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Step 1 & 2: Load Observations and Forecasts
    obs_path = raw_dir / "observations" / "coimbatore_station_observations.csv"
    fc_path = raw_dir / "forecasts" / "coimbatore_historical_forecasts.csv"
    master_grid_path = proc_dir / "geospatial" / "geospatial_features_master.csv"

    obs_df = load_observations(obs_path)
    fc_df = load_forecasts(fc_path)

    # Step 3: Spatial & Temporal Alignment
    matchup_df, match_stats = match_observations_and_forecasts(obs_df, fc_df, master_grid_path, config)

    # Step 4: Baseline Ladder Calculations
    logger.info("Computing B0 Coarse Forecast Baseline...")
    matchup_df = compute_b0_coarse(matchup_df)

    logger.info("Computing B1 Bilinear Interpolation Baseline...")
    matchup_df = compute_b1_bilinear(matchup_df, fc_df, config)

    logger.info("Computing B2 Elevation Lapse-Rate Correction Baseline...")
    matchup_df = compute_b2_lapse_rate(matchup_df, config)

    logger.info("Computing B3 Quantile Mapping Baseline (fitted on TRAIN)...")
    matchup_df = compute_b3_quantile_mapping(matchup_df, config)

    logger.info("Computing residual targets for future Phase 4 ML...")
    matchup_df = compute_residuals(matchup_df)

    # Step 5: Execute Quality Assurance Checks A through Q
    validator = MatchupValidator(matchup_df)
    qa_report = validator.validate()

    with open(meta_dir / "validation_phase3_matchups.json", "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2)

    # Step 6: Calculate Descriptive Baseline Metrics across TRAIN, CALIBRATION, TEST splits
    metric_rows = []
    splits = ["TRAIN", "CALIBRATION", "TEST"]
    baselines = [
        ("B0", "b0_temperature", "b0_humidity"),
        ("B1", "b1_temperature", "b1_humidity"),
        ("B2", "b2_temperature", "b2_humidity"),
        ("B3", "b3_temperature", "b3_humidity"),
    ]

    for b_name, temp_col, hum_col in baselines:
        for s in splits:
            sub = matchup_df[matchup_df["split"] == s]
            # Temperature evaluation (VALID records only)
            t_eval = sub[sub["qc_status"] == "VALID"]
            t_metrics = calculate_metrics(t_eval, temp_col, "observed_temperature")
            h_metrics = calculate_metrics(t_eval, hum_col, "observed_humidity")

            metric_rows.append({
                "model": b_name,
                "split": s,
                "record_count": len(sub),
                "valid_count": len(t_eval),
                "temp_mae": t_metrics["mae"],
                "temp_rmse": t_metrics["rmse"],
                "temp_bias": t_metrics["bias"],
                "hum_mae": h_metrics["mae"],
                "hum_rmse": h_metrics["rmse"],
                "hum_bias": h_metrics["bias"],
            })

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(matchups_dir / "baseline_metrics_summary.csv", index=False)

    # Save Master Matchup CSV
    # Select standardized output column ordering
    output_cols = [
        "station_id", "station_group", "observation_time", "forecast_issue_time", "valid_time", "lead_time_hours",
        "latitude_obs", "longitude_obs", "grid_id", "panchayat_id", "forecast_parent_id",
        "station_elevation", "grid_elevation", "observed_temperature", "observed_humidity", "observed_rainfall",
        "forecast_temperature", "forecast_humidity", "forecast_rainfall",
        "b0_temperature", "b0_humidity", "b0_rainfall",
        "b1_temperature", "b1_humidity", "b1_rainfall", "b1_status",
        "b2_temperature", "b2_humidity",
        "b3_temperature", "b3_humidity",
        "residual_temperature", "residual_humidity",
        "qc_status", "split", "data_status"
    ]
    # Retain existing columns cleanly
    avail_cols = [c for c in output_cols if c in matchup_df.columns]
    matchup_df[avail_cols].to_csv(matchups_dir / "weather_matchups.csv", index=False)

    # Save Station Alignment Summary
    stn_summary = matchup_df[["station_id", "grid_id", "panchayat_id", "forecast_parent_id", "station_elevation", "grid_elevation"]].drop_duplicates().reset_index(drop=True)
    stn_summary.to_csv(matchups_dir / "station_alignment_summary.csv", index=False)

    logger.info("Saved master matchup datasets to %s", matchups_dir)
    logger.info("Phase 3 Build Complete! QA Valid=%s", qa_report["is_valid"])


if __name__ == "__main__":
    main()
