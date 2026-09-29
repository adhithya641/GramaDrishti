"""
GramDrishti — Phase 6 Pipeline Execution Script
Builds and validates rainfall probability models (R0, R1, R2 raw, R2 calibrated),
performs station and lead-time diagnostic analysis, and executes 1-km grid prediction
and Panchayat spatial aggregation across all 180 Gram Panchayats.
"""

import os
import sys
import json
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
import numpy as np
import pandas as pd

from src.ml.feature_builder import (
    load_and_merge_datasets,
    add_temporal_features,
    validate_feature_leakage
)
from src.ml.rainfall_data import (
    create_rainfall_targets,
    audit_rainfall_data,
    get_split_event_summary
)
from src.ml.rainfall_models import (
    ClimatologyModel,
    LogisticRegressionModel,
    LightGBMRainfallModel,
    IsotonicCalibrator
)
from src.ml.rainfall_evaluator import (
    evaluate_model_performance,
    compute_reliability_curve,
    analyze_station_performance,
    analyze_lead_time_performance,
    analyze_monthly_performance
)
from src.ml.panchayat_aggregator import (
    aggregate_grid_to_panchayats,
    build_full_grid_features
)


def run_phase6_pipeline():
    print("=" * 70)
    print("GRAMDRISHTI — PHASE 6: RAINFALL PROBABILITY & PANCHAYAT AGGREGATION")
    print("=" * 70)

    # 1. Load Config
    config_path = "configs/rainfall_config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # 2. Load & Merge Datasets
    print("[1/9] Loading matchups and geospatial features...")
    df = load_and_merge_datasets(
        config["paths"]["matchups_csv"],
        config["paths"]["geospatial_master_csv"]
    )
    df = add_temporal_features(df, "observation_time")
    df = create_rainfall_targets(df)

    # 3. Data Audit & Split Event Summary
    print("[2/9] Performing data quality audit and split event analysis...")
    audit_results = audit_rainfall_data(df)
    print(f"   - Audit clean status: {audit_results['clean_data']}")
    print(f"   - Total records: {audit_results['total_records']}, Missing: {audit_results['missing_observed_rainfall']}, Duplicates: {audit_results['duplicate_records']}")

    # Apply Chronological Split
    split_cfg = config["temporal_split"]
    obs_times = pd.to_datetime(df["observation_time"])
    df.loc[(obs_times >= split_cfg["train_start"]) & (obs_times <= split_cfg["train_end"]), "split"] = "TRAIN"
    df.loc[(obs_times >= split_cfg["calibration_start"]) & (obs_times <= split_cfg["calibration_end"]), "split"] = "CALIBRATION"
    df.loc[(obs_times >= split_cfg["test_start"]) & (obs_times <= split_cfg["test_end"]), "split"] = "TEST"

    event_summary = get_split_event_summary(df)

    print("\n   Rainfall Event Rates:")
    for tgt, splits_info in event_summary.items():
        print(f"   === Target: {tgt} ===")
        for sp, stats in splits_info.items():
            print(f"     {sp:11s}: {stats['events']:4d} / {stats['total']:4d} events ({stats['event_rate_pct']:.2f}%)")

    # 4. Prepare Feature Matrix
    print("\n[3/9] Preparing feature matrix & validating leakage rules...")
    feat_cfg = config["features"]
    feature_cols = feat_cfg["forecast"] + feat_cfg["geospatial"] + feat_cfg["temporal"]
    cat_cols = feat_cfg.get("categorical", [])

    validate_feature_leakage(feature_cols, config["strictly_forbidden_features"])

    # Prepare DataFrame splits
    train_df = df[df["split"] == "TRAIN"].copy()
    calib_df = df[df["split"] == "CALIBRATION"].copy()
    test_df = df[df["split"] == "TEST"].copy()

    X_train = train_df[feature_cols].copy()
    X_calib = calib_df[feature_cols].copy()
    X_test = test_df[feature_cols].copy()
    X_full = df[feature_cols].copy()

    for c in cat_cols:
        if c in X_train.columns:
            X_train[c] = X_train[c].astype("category")
            X_calib[c] = X_calib[c].astype("category")
            X_test[c] = X_test[c].astype("category")
            X_full[c] = X_full[c].astype("category")

    targets = ["rain_1mm", "rain_10mm", "rain_25mm"]
    models_r0 = {}
    models_r1 = {}
    models_r2 = {}
    calibrators = {}

    eval_results = []
    reliability_curves = {}

    # Store predictions on test set
    test_probs = {
        "r0": {},
        "r1": {},
        "r2_raw": {},
        "r2_calibrated": {}
    }

    print("[4/9] Fitting models R0, R1, R2 on TRAIN and calibrating on CALIBRATION...")
    for target in targets:
        y_train = train_df[target].values
        y_calib = calib_df[target].values
        y_test = test_df[target].values

        # R0 Climatology
        r0 = ClimatologyModel().fit(y_train)
        models_r0[target] = r0
        p_r0_test = r0.predict_proba(X_test)
        test_probs["r0"][target] = p_r0_test

        # R1 Logistic Regression
        r1 = LogisticRegressionModel(config["model_params"]["logistic"]).fit(X_train, y_train)
        models_r1[target] = r1
        p_r1_test = r1.predict_proba(X_test)
        test_probs["r1"][target] = p_r1_test

        # R2 LightGBM Classifier
        r2 = LightGBMRainfallModel(config["model_params"]["lgb"]).fit(X_train, y_train)
        models_r2[target] = r2
        p_r2_raw_test = r2.predict_proba(X_test)
        test_probs["r2_raw"][target] = p_r2_raw_test

        # Isotonic Calibration on CALIBRATION set
        p_r2_raw_calib = r2.predict_proba(X_calib)
        calibrator = IsotonicCalibrator().fit(p_r2_raw_calib, y_calib)
        calibrators[target] = calibrator
        p_r2_calib_test = calibrator.transform(p_r2_raw_test)
        test_probs["r2_calibrated"][target] = p_r2_calib_test

        # Evaluate on TEST
        eval_r0 = evaluate_model_performance(p_r0_test, y_test, "R0 Climatology", target, "TEST")
        eval_r1 = evaluate_model_performance(p_r1_test, y_test, "R1 Logistic Regression", target, "TEST")
        eval_r2_raw = evaluate_model_performance(p_r2_raw_test, y_test, "R2 LightGBM Raw", target, "TEST")
        eval_r2_calib = evaluate_model_performance(p_r2_calib_test, y_test, "R2 LightGBM Calibrated", target, "TEST")

        eval_results.extend([eval_r0, eval_r1, eval_r2_raw, eval_r2_calib])

        reliability_curves[target] = {
            "R0": compute_reliability_curve(p_r0_test, y_test),
            "R1": compute_reliability_curve(p_r1_test, y_test),
            "R2_Raw": compute_reliability_curve(p_r2_raw_test, y_test),
            "R2_Calibrated": compute_reliability_curve(p_r2_calib_test, y_test)
        }

    eval_df = pd.DataFrame(eval_results)
    print("\n" + "-" * 75)
    print("TEST PERIOD METRICS SUMMARY:")
    print("-" * 75)
    print(eval_df[["threshold", "model", "brier_score", "pod", "far", "csi", "predicted_prob_mean", "observed_rate"]].to_string(index=False))
    print("-" * 75 + "\n")

    # 5. Station, Lead Time & Monthly Analysis for R2 Calibrated
    print("[5/9] Running station, lead-time, and monthly diagnostic analyses...")
    stn_analysis = analyze_station_performance(test_df, test_probs["r2_calibrated"], targets)
    lead_analysis = analyze_lead_time_performance(test_df, test_probs["r2_calibrated"], targets)
    monthly_analysis = analyze_monthly_performance(test_df, test_probs["r2_calibrated"], targets)

    # 6. Station Predictions Export
    print("[6/9] Generating station predictions dataset...")
    df_pred = df.copy()
    for target in targets:
        # Full dataset predictions
        p_r2_raw_full = models_r2[target].predict_proba(X_full)
        p_r2_calib_full = calibrators[target].transform(p_r2_raw_full)

        df_pred[f"r0_prob_{target}"] = models_r0[target].predict_proba(X_full)
        df_pred[f"r1_prob_{target}"] = models_r1[target].predict_proba(X_full)
        df_pred[f"r2_raw_prob_{target}"] = p_r2_raw_full
        df_pred[f"r2_calib_prob_{target}"] = p_r2_calib_full

    os.makedirs(os.path.dirname(config["paths"]["station_predictions_csv"]), exist_ok=True)
    df_pred.to_csv(config["paths"]["station_predictions_csv"], index=False)
    print(f"   Saved station predictions to: {config['paths']['station_predictions_csv']}")

    # 7. Grid Prediction & Panchayat Aggregation
    print("[7/9] Generating 1-km grid predictions and aggregating across 180 Panchayats...")
    geo_master = pd.read_csv(config["paths"]["geospatial_master_csv"])
    forecasts = pd.read_csv(config["paths"]["forecasts_processed_csv"])
    mapping = pd.read_csv(config["paths"]["forecast_grid_mapping_csv"])

    test_timestamps = sorted(test_df["observation_time"].unique())
    full_grid_df = build_full_grid_features(geo_master, forecasts, mapping, test_timestamps)

    X_grid = full_grid_df[feature_cols].copy()
    for c in cat_cols:
        if c in X_grid.columns:
            X_grid[c] = X_grid[c].astype("category")

    grid_pred_df = full_grid_df[["grid_id", "panchayat_id", "observation_time", "lead_time_hours"]].copy()

    for target in targets:
        t_name = config["threshold_names"][float(target.replace("rain_", "").replace("mm", ""))]
        p_raw = models_r2[target].predict_proba(X_grid)
        p_calib = calibrators[target].transform(p_raw)
        grid_pred_df[f"prob_{t_name}"] = p_calib

    panchayat_df = aggregate_grid_to_panchayats(grid_pred_df)

    panchayat_out_path = config["paths"]["panchayat_predictions_csv"]
    os.makedirs(os.path.dirname(panchayat_out_path), exist_ok=True)
    panchayat_df.to_csv(panchayat_out_path, index=False)
    print(f"   Aggregated {len(panchayat_df)} Panchayat forecast records across {panchayat_df['panchayat_id'].nunique()} unique Panchayats.")
    print(f"   Saved Panchayat predictions to: {panchayat_out_path}")

    # 8. Save Artifacts & Reports
    print("[8/9] Saving model text files and metadata reports...")
    proc_models_dir = config["paths"]["processed_models_dir"]
    os.makedirs(proc_models_dir, exist_ok=True)

    eval_df.to_csv(os.path.join(proc_models_dir, "model_metrics_comparison.csv"), index=False)
    stn_analysis.to_csv(os.path.join(proc_models_dir, "station_performance_rainfall.csv"), index=False)
    lead_analysis.to_csv(os.path.join(proc_models_dir, "lead_time_performance_rainfall.csv"), index=False)
    monthly_analysis.to_csv(os.path.join(proc_models_dir, "monthly_performance_rainfall.csv"), index=False)

    val_json = {
        "record_counts": {
            "train": len(train_df),
            "calibration": len(calib_df),
            "test": len(test_df),
            "total": len(df)
        },
        "data_audit": audit_results,
        "event_summary": event_summary,
        "test_metrics": eval_df.to_dict(orient="records"),
        "reliability_curves": reliability_curves,
        "panchayat_aggregation_stats": {
            "total_records": len(panchayat_df),
            "unique_panchayats": int(panchayat_df["panchayat_id"].nunique()),
            "status_counts": panchayat_df["aggregation_status"].value_counts().to_dict()
        }
    }

    val_json_path = config["paths"]["validation_json"]
    os.makedirs(os.path.dirname(val_json_path), exist_ok=True)
    with open(val_json_path, "w") as f:
        json.dump(val_json, f, indent=2)

    print(f"   Saved validation metadata report to: {val_json_path}")
    print("[9/9] Phase 6 Rainfall Pipeline executed successfully!")

    return df, eval_df, panchayat_df, val_json


if __name__ == "__main__":
    run_phase6_pipeline()
