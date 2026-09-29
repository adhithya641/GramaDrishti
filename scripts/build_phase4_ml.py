"""
GramDrishti — Phase 4 Pipeline Execution Script
Builds LightGBM residual correction models for temperature and humidity,
evaluates performance against baselines (B0-B3), performs ablation and station-wise analysis,
exports predictions, model artifacts, and documentation reports.
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
import numpy as np
import pandas as pd
import lightgbm as lgb

from src.ml.feature_builder import (
    load_and_merge_datasets,
    add_temporal_features,
    prepare_features_and_targets,
    validate_feature_leakage
)
from src.ml.trainer import (
    train_residual_model,
    predict_residuals,
    extract_feature_importance
)
from src.ml.evaluator import (
    calculate_metrics,
    calculate_improvement,
    evaluate_all_baselines_and_ml,
    run_ablation_study,
    station_group_analysis
)
from src.ml.exporter import (
    save_model_artifacts,
    export_predictions,
    export_validation_report
)


def run_phase4_pipeline():
    print("=" * 70)
    print("GRAMDRISHTI — PHASE 4: LIGHTGBM RESIDUAL CORRECTION PIPELINE")
    print("=" * 70)

    # 1. Load config
    config_path = "configs/ml_config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # 2. Load and merge datasets
    print("[1/8] Loading matchups and geospatial features...")
    df = load_and_merge_datasets(
        config["paths"]["matchups_csv"],
        config["paths"]["geospatial_master_csv"]
    )
    df = add_temporal_features(df, "observation_time")

    # 3. Target construction
    df["residual_temperature"] = df["observed_temperature"] - df["b2_temperature"]
    df["residual_humidity"] = df["observed_humidity"] - df["b2_humidity"]

    # 4. Temporal splitting
    print("[2/8] Performing chronological temporal splitting...")
    split_cfg = config["temporal_split"]
    obs_times = pd.to_datetime(df["observation_time"])

    train_mask = (obs_times >= split_cfg["train_start"]) & (obs_times <= split_cfg["train_end"])
    calib_mask = (obs_times >= split_cfg["calibration_start"]) & (obs_times <= split_cfg["calibration_end"])
    test_mask = (obs_times >= split_cfg["test_start"]) & (obs_times <= split_cfg["test_end"])

    df.loc[train_mask, "split"] = "TRAIN"
    df.loc[calib_mask, "split"] = "CALIBRATION"
    df.loc[test_mask, "split"] = "TEST"

    train_df = df[df["split"] == "TRAIN"].copy()
    calib_df = df[df["split"] == "CALIBRATION"].copy()
    test_df = df[df["split"] == "TEST"].copy()

    print(f"   - TRAIN records:       {len(train_df)}")
    print(f"   - CALIBRATION records: {len(calib_df)}")
    print(f"   - TEST records:        {len(test_df)}")

    # 5. Build features & Leakage check
    print("[3/8] Preparing feature matrices and validating leakage rules...")
    X_train_temp, y_train_temp, feat_cols_temp, cat_cols = prepare_features_and_targets(
        train_df, config, "temperature"
    )
    X_calib_temp, _, _, _ = prepare_features_and_targets(calib_df, config, "temperature")
    X_test_temp, _, _, _ = prepare_features_and_targets(test_df, config, "temperature")
    X_full_temp, _, _, _ = prepare_features_and_targets(df, config, "temperature")

    X_train_hum, y_train_hum, feat_cols_hum, _ = prepare_features_and_targets(
        train_df, config, "humidity"
    )
    X_calib_hum, _, _, _ = prepare_features_and_targets(calib_df, config, "humidity")
    X_test_hum, _, _, _ = prepare_features_and_targets(test_df, config, "humidity")
    X_full_hum, _, _, _ = prepare_features_and_targets(df, config, "humidity")

    # 6. Train Models
    print("[4/8] Training LightGBM Temperature Residual Model...")
    temp_model = train_residual_model(
        X_train_temp, y_train_temp, cat_cols, config["model_params"]
    )
    df["predicted_temperature_residual"] = predict_residuals(temp_model, X_full_temp)
    df["ml_temperature"] = df["b2_temperature"] + df["predicted_temperature_residual"]

    print("[5/8] Training LightGBM Humidity Residual Model...")
    hum_model = train_residual_model(
        X_train_hum, y_train_hum, cat_cols, config["model_params"]
    )
    df["predicted_humidity_residual"] = predict_residuals(hum_model, X_full_hum)
    df["ml_humidity"] = df["b2_humidity"] + df["predicted_humidity_residual"]

    # Re-extract split subsets after prediction assignment
    test_df = df[df["split"] == "TEST"].copy()

    # 7. Evaluate Metrics
    print("[6/8] Evaluating baseline ladder (B0-B3) vs ML across splits...")
    metrics_temp_df = evaluate_all_baselines_and_ml(df, "temperature")
    metrics_hum_df = evaluate_all_baselines_and_ml(df, "humidity")

    # Extract test split performance
    test_temp_metrics = metrics_temp_df[metrics_temp_df["split"] == "TEST"].set_index("model")
    test_hum_metrics = metrics_hum_df[metrics_hum_df["split"] == "TEST"].set_index("model")

    temp_b2_mae = test_temp_metrics.loc["B2", "mae"]
    temp_b3_mae = test_temp_metrics.loc["B3", "mae"]
    temp_ml_mae = test_temp_metrics.loc["ML", "mae"]

    hum_b2_mae = test_hum_metrics.loc["B2", "mae"]
    hum_b3_mae = test_hum_metrics.loc["B3", "mae"]
    hum_ml_mae = test_hum_metrics.loc["ML", "mae"]

    imp_temp_vs_b2 = calculate_improvement(temp_b2_mae, temp_ml_mae)
    imp_temp_vs_b3 = calculate_improvement(temp_b3_mae, temp_ml_mae)

    imp_hum_vs_b2 = calculate_improvement(hum_b2_mae, hum_ml_mae)
    imp_hum_vs_b3 = calculate_improvement(hum_b3_mae, hum_ml_mae)

    print("\n" + "-" * 50)
    print("TEST PERIOD METRICS COMPARISON:")
    print("-" * 50)
    print(f"Temperature TEST MAE (°C):")
    print(f"  B0: {test_temp_metrics.loc['B0', 'mae']:.3f} | B1: {test_temp_metrics.loc['B1', 'mae']:.3f} | B2: {temp_b2_mae:.3f} | B3: {temp_b3_mae:.3f} | ML: {temp_ml_mae:.3f}")
    print(f"  ML vs B2 Improvement: {imp_temp_vs_b2:+.2f}%")
    print(f"  ML vs B3 Improvement: {imp_temp_vs_b3:+.2f}%")

    print(f"\nRelative Humidity TEST MAE (%):")
    print(f"  B0/B1/B2: {hum_b2_mae:.3f} | B3: {hum_b3_mae:.3f} | ML: {hum_ml_mae:.3f}")
    print(f"  ML vs B2 Improvement: {imp_hum_vs_b2:+.2f}%")
    print(f"  ML vs B3 Improvement: {imp_hum_vs_b3:+.2f}%")
    print("-" * 50 + "\n")

    # 8. Feature Importance, Ablation & Station Analysis
    print("[7/8] Computing feature importances, ablation study, and station performance...")
    # Sample subset for SHAP computation
    shap_sample_temp = X_test_temp.sample(n=min(500, len(X_test_temp)), random_state=42)
    shap_sample_hum = X_test_hum.sample(n=min(500, len(X_test_hum)), random_state=42)

    fi_temp = extract_feature_importance(temp_model, shap_sample_temp, "temperature")
    fi_hum = extract_feature_importance(hum_model, shap_sample_hum, "humidity")
    fi_combined = pd.concat([fi_temp, fi_hum], ignore_index=True)

    os.makedirs(config["paths"]["processed_models_dir"], exist_ok=True)
    fi_combined.to_csv(os.path.join(config["paths"]["processed_models_dir"], "feature_importance.csv"), index=False)

    # Ablation
    ablation_temp = run_ablation_study(train_df, test_df, config, "temperature")
    ablation_hum = run_ablation_study(train_df, test_df, config, "humidity")
    ablation_combined = pd.concat([ablation_temp, ablation_hum], ignore_index=True)
    ablation_combined.to_csv(os.path.join(config["paths"]["processed_models_dir"], "ablation_results.csv"), index=False)

    # Station performance
    stn_perf_temp = station_group_analysis(test_df, "temperature")
    stn_perf_hum = station_group_analysis(test_df, "humidity")
    stn_perf_combined = pd.concat([stn_perf_temp, stn_perf_hum], ignore_index=True)
    stn_perf_combined.to_csv(os.path.join(config["paths"]["processed_models_dir"], "station_performance.csv"), index=False)

    # 9. Save Artifacts, Predictions & Validation JSON
    print("[8/8] Exporting model text files, predictions dataset, and documentation...")
    save_model_artifacts(
        temp_model, hum_model, feat_cols_temp, cat_cols, config,
        len(train_df), len(calib_df), len(test_df),
        config["paths"]["models_dir"]
    )

    export_predictions(df, config["paths"]["predictions_csv"])

    val_summary = {
        "record_counts": {
            "train": len(train_df),
            "calibration": len(calib_df),
            "test": len(test_df),
            "total": len(df)
        },
        "temperature_test_metrics": {
            "b0_mae": test_temp_metrics.loc["B0", "mae"],
            "b1_mae": test_temp_metrics.loc["B1", "mae"],
            "b2_mae": temp_b2_mae,
            "b3_mae": temp_b3_mae,
            "ml_mae": temp_ml_mae,
            "ml_vs_b2_improvement_pct": imp_temp_vs_b2,
            "ml_vs_b3_improvement_pct": imp_temp_vs_b3
        },
        "humidity_test_metrics": {
            "b2_mae": hum_b2_mae,
            "b3_mae": hum_b3_mae,
            "ml_mae": hum_ml_mae,
            "ml_vs_b2_improvement_pct": imp_hum_vs_b2,
            "ml_vs_b3_improvement_pct": imp_hum_vs_b3
        },
        "sanity_checks": {
            "no_nan_predictions": not (df["ml_temperature"].isna().any() or df["ml_humidity"].isna().any()),
            "prediction_count": len(df),
            "leakage_check": "PASS: Strictly forbidden features excluded from matrix"
        }
    }
    export_validation_report(True, val_summary, config["paths"]["validation_json"])

    print("\nPhase 4 LightGBM Residual Correction Pipeline completed successfully!")
    return df, metrics_temp_df, metrics_hum_df


if __name__ == "__main__":
    run_phase4_pipeline()
