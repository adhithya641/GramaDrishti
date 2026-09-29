"""
GramDrishti — Phase 4 Artifact & Prediction Exporter
Saves trained LightGBM model text files, feature schema, training metadata,
predictions dataset, and validation reports.
"""

from typing import Dict, Any, List
import os
import json
import datetime
import pandas as pd
import lightgbm as lgb
import yaml


def save_model_artifacts(
    temp_model: lgb.LGBMRegressor,
    hum_model: lgb.LGBMRegressor,
    feature_cols: List[str],
    cat_cols: List[str],
    config: Dict[str, Any],
    train_count: int,
    calib_count: int,
    test_count: int,
    output_dir: str = "models/"
) -> None:
    """
    Save LightGBM model text files, feature schema, and training metadata to models/ directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    # 1. Save model text files
    temp_model.booster_.save_model(os.path.join(output_dir, "temperature_residual_model.txt"))
    hum_model.booster_.save_model(os.path.join(output_dir, "humidity_residual_model.txt"))

    # 2. Save model config YAML
    with open(os.path.join(output_dir, "model_config.yaml"), "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # 3. Save feature schema JSON
    schema_data = {
        "feature_count": len(feature_cols),
        "feature_list": feature_cols,
        "categorical_features": cat_cols,
        "strictly_forbidden_features": config.get("strictly_forbidden_features", [])
    }
    with open(os.path.join(output_dir, "feature_schema.json"), "w") as f:
        json.dump(schema_data, f, indent=2)

    # 4. Save training metadata JSON
    metadata = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_dataset": config["paths"]["matchups_csv"],
        "geospatial_source": config["paths"]["geospatial_master_csv"],
        "targets": {
            "temperature_residual": "observed_temperature - b2_temperature",
            "humidity_residual": "observed_humidity - b2_humidity"
        },
        "temporal_splits": config["temporal_split"],
        "random_seed": config["model_params"].get("random_state", 42),
        "lightgbm_version": lgb.__version__,
        "counts": {
            "train_records": train_count,
            "calibration_records": calib_count,
            "test_records": test_count,
            "total_records": train_count + calib_count + test_count
        }
    }
    with open(os.path.join(output_dir, "training_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)


def export_predictions(
    df: pd.DataFrame,
    output_path: str = "data/processed/predictions/weather_predictions.csv"
) -> None:
    """
    Export predictions dataset containing all baselines (B0-B3), ML predictions,
    and residual targets/predictions across all splits.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    required_cols = [
        "station_id", "observation_time", "valid_time", "lead_time_hours",
        "grid_id", "panchayat_id",
        "observed_temperature", "b0_temperature", "b1_temperature", "b2_temperature", "b3_temperature", "ml_temperature",
        "observed_humidity", "b0_humidity", "b1_humidity", "b2_humidity", "b3_humidity", "ml_humidity",
        "residual_temperature", "predicted_temperature_residual",
        "residual_humidity", "predicted_humidity_residual",
        "split"
    ]

    out_df = df[required_cols].copy()
    out_df.to_csv(output_path, index=False)


def export_validation_report(
    is_valid: bool,
    summary: Dict[str, Any],
    output_path: str = "data/metadata/validation_phase4_ml.json"
) -> None:
    """
    Save validation report for Phase 4 ML execution.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "is_valid": is_valid,
        "phase": 4,
        "summary": summary
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
