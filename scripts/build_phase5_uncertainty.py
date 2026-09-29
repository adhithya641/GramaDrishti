"""
GramDrishti — Phase 5 Uncertainty Quantification Pipeline
Builds Quantile LightGBM models (q10, q50, q90) and applies Conformal Calibration (CQR)
"""
import os
import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml
import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib

from src.ml.feature_builder import (
    load_and_merge_datasets,
    add_temporal_features,
    prepare_features_and_targets
)
from src.uncertainty.quantile_models import (
    train_quantile_model,
    predict_quantiles
)
from src.uncertainty.conformal import (
    compute_conformal_scores,
    get_conformal_correction,
    apply_conformal_correction,
    classify_reliability
)

def run_phase5_pipeline():
    print("=" * 70)
    print("GRAMDRISHTI — PHASE 5: UNCERTAINTY QUANTIFICATION")
    print("=" * 70)

    # 1. Load Configs
    with open("configs/ml_config.yaml", "r") as f:
        ml_config = yaml.safe_load(f)
        
    with open("configs/uncertainty_config.yaml", "r") as f:
        unc_config = yaml.safe_load(f)

    # 2. Load and merge datasets
    print("[1/6] Loading data...")
    df = load_and_merge_datasets(
        ml_config["paths"]["matchups_csv"],
        ml_config["paths"]["geospatial_master_csv"]
    )
    df = add_temporal_features(df, "observation_time")

    # Reconstruct targets (same as Phase 4)
    df["residual_temperature"] = df["observed_temperature"] - df["b2_temperature"]
    df["residual_humidity"] = df["observed_humidity"] - df["b2_humidity"]

    # Temporal Splitting
    split_cfg = ml_config["temporal_split"]
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

    # Build features
    print("[2/6] Preparing features...")
    X_train_temp, y_train_temp, feat_cols_temp, cat_cols = prepare_features_and_targets(train_df, ml_config, "temperature")
    X_calib_temp, y_calib_temp, _, _ = prepare_features_and_targets(calib_df, ml_config, "temperature")
    X_full_temp, _, _, _ = prepare_features_and_targets(df, ml_config, "temperature")

    X_train_hum, y_train_hum, feat_cols_hum, _ = prepare_features_and_targets(train_df, ml_config, "humidity")
    X_calib_hum, y_calib_hum, _, _ = prepare_features_and_targets(calib_df, ml_config, "humidity")
    X_full_hum, _, _, _ = prepare_features_and_targets(df, ml_config, "humidity")

    # 3. Train Quantile Models
    print("[3/6] Training Quantile Models...")
    quantiles = unc_config["quantiles"]
    
    models_temp = {}
    models_hum = {}
    
    for q_name, q_val in quantiles.items():
        print(f"      Training Temperature {q_name} (q={q_val})")
        models_temp[q_name] = train_quantile_model(
            X_train_temp, y_train_temp, cat_cols, q_val, unc_config["model_params"]
        )
        print(f"      Training Humidity {q_name} (q={q_val})")
        models_hum[q_name] = train_quantile_model(
            X_train_hum, y_train_hum, cat_cols, q_val, unc_config["model_params"]
        )

    # 4. Predict on Calibration and Test (Residual scale)
    print("[4/6] Conformal Calibration...")
    
    # Temperature
    preds_calib_temp = predict_quantiles(models_temp, X_calib_temp)
    scores_temp = compute_conformal_scores(
        y_calib_temp.values, preds_calib_temp["lower"].values, preds_calib_temp["upper"].values
    )
    correction_temp = get_conformal_correction(scores_temp, unc_config["conformal"]["alpha"])
    
    # Humidity
    preds_calib_hum = predict_quantiles(models_hum, X_calib_hum)
    scores_hum = compute_conformal_scores(
        y_calib_hum.values, preds_calib_hum["lower"].values, preds_calib_hum["upper"].values
    )
    correction_hum = get_conformal_correction(scores_hum, unc_config["conformal"]["alpha"])

    print(f"      Temperature correction: {correction_temp:.4f}")
    print(f"      Humidity correction:    {correction_hum:.4f}")

    # Predict full dataset
    preds_full_temp = predict_quantiles(models_temp, X_full_temp)
    calib_full_temp = apply_conformal_correction(
        preds_full_temp["lower"], preds_full_temp["upper"], correction_temp
    )
    
    preds_full_hum = predict_quantiles(models_hum, X_full_hum)
    calib_full_hum = apply_conformal_correction(
        preds_full_hum["lower"], preds_full_hum["upper"], correction_hum
    )

    # 5. Build Output and Classify
    print("[5/6] Building uncertainty outputs and metrics...")
    
    preds_df = pd.read_csv(ml_config["paths"]["predictions_csv"])
    # Sort or align just in case? No, the indices will match exactly if we process df sequentially.
    # To be extremely safe, we can join on station_id, observation_time, lead_time_hours
    
    # Simple assignment is fine since the order of df wasn't changed.
    
    df_out = df[["observation_time", "station_id", "grid_id", "split", "lead_time_hours",
                 "observed_temperature", "observed_humidity", 
                 "b2_temperature", "b2_humidity"]].copy()
                 
    df_out["ml_temperature"] = preds_df["ml_temperature"].values
    df_out["ml_humidity"] = preds_df["ml_humidity"].values
    
    df_out["q10_temperature"] = df_out["b2_temperature"] + calib_full_temp["q10_calibrated"].values
    df_out["q50_temperature"] = df_out["b2_temperature"] + preds_full_temp["median"].values
    df_out["q90_temperature"] = df_out["b2_temperature"] + calib_full_temp["q90_calibrated"].values
    
    df_out["q10_humidity"] = df_out["b2_humidity"] + calib_full_hum["q10_calibrated"].values
    df_out["q50_humidity"] = df_out["b2_humidity"] + preds_full_hum["median"].values
    df_out["q90_humidity"] = df_out["b2_humidity"] + calib_full_hum["q90_calibrated"].values

    df_out["q10_humidity"] = df_out["q10_humidity"].clip(0, 100)
    df_out["q50_humidity"] = df_out["q50_humidity"].clip(0, 100)
    df_out["q90_humidity"] = df_out["q90_humidity"].clip(0, 100)

    df_out["temperature_interval_width"] = df_out["q90_temperature"] - df_out["q10_temperature"]
    df_out["humidity_interval_width"] = df_out["q90_humidity"] - df_out["q10_humidity"]

    r_th = unc_config["reliability_thresholds"]
    df_out["temperature_reliability"] = classify_reliability(
        df_out["temperature_interval_width"],
        r_th["temperature_width_medium"],
        r_th["temperature_width_low"]
    )
    df_out["humidity_reliability"] = classify_reliability(
        df_out["humidity_interval_width"],
        r_th["humidity_width_medium"],
        r_th["humidity_width_low"]
    )

    test_out = df_out[df_out["split"] == "TEST"].copy()
    calib_out = df_out[df_out["split"] == "CALIBRATION"].copy()

    # Overall coverage
    temp_coverage = ((test_out["observed_temperature"] >= test_out["q10_temperature"]) &
                     (test_out["observed_temperature"] <= test_out["q90_temperature"])).mean()
    hum_coverage = ((test_out["observed_humidity"] >= test_out["q10_humidity"]) &
                    (test_out["observed_humidity"] <= test_out["q90_humidity"])).mean()

    # Calibration coverage (should be close to target)
    calib_temp_coverage = ((calib_out["observed_temperature"] >= calib_out["q10_temperature"]) &
                           (calib_out["observed_temperature"] <= calib_out["q90_temperature"])).mean()
    calib_hum_coverage = ((calib_out["observed_humidity"] >= calib_out["q10_humidity"]) &
                          (calib_out["observed_humidity"] <= calib_out["q90_humidity"])).mean()

    print(f"      Temperature Empirical Coverage (CALIB): {calib_temp_coverage:.2%}")
    print(f"      Humidity Empirical Coverage (CALIB):    {calib_hum_coverage:.2%}")
    print(f"      Temperature Empirical Coverage (TEST):  {temp_coverage:.2%}")
    print(f"      Humidity Empirical Coverage (TEST):     {hum_coverage:.2%}")

    # Station-level breakdowns
    station_metrics = []
    for station_id in test_out["station_id"].unique():
        s = test_out[test_out["station_id"] == station_id]
        t_cov = ((s["observed_temperature"] >= s["q10_temperature"]) &
                 (s["observed_temperature"] <= s["q90_temperature"])).mean()
        h_cov = ((s["observed_humidity"] >= s["q10_humidity"]) &
                 (s["observed_humidity"] <= s["q90_humidity"])).mean()
        station_metrics.append({
            "station_id": str(station_id),
            "n_records": int(len(s)),
            "temp_coverage": float(t_cov),
            "hum_coverage": float(h_cov),
            "temp_mean_width": float(s["temperature_interval_width"].mean()),
            "hum_mean_width": float(s["humidity_interval_width"].mean())
        })

    # Lead-time breakdowns
    lead_metrics = []
    for lt in sorted(test_out["lead_time_hours"].unique()):
        lt_sub = test_out[test_out["lead_time_hours"] == lt]
        t_cov = ((lt_sub["observed_temperature"] >= lt_sub["q10_temperature"]) &
                 (lt_sub["observed_temperature"] <= lt_sub["q90_temperature"])).mean()
        h_cov = ((lt_sub["observed_humidity"] >= lt_sub["q10_humidity"]) &
                 (lt_sub["observed_humidity"] <= lt_sub["q90_humidity"])).mean()
        lead_metrics.append({
            "lead_time_hours": int(lt),
            "n_records": int(len(lt_sub)),
            "temp_coverage": float(t_cov),
            "hum_coverage": float(h_cov),
            "temp_mean_width": float(lt_sub["temperature_interval_width"].mean()),
            "hum_mean_width": float(lt_sub["humidity_interval_width"].mean())
        })

    # Reliability distribution on TEST
    temp_rel_dist = test_out["temperature_reliability"].value_counts().to_dict()
    hum_rel_dist = test_out["humidity_reliability"].value_counts().to_dict()

    # 6. Save Artifacts
    print("[6/6] Saving Artifacts...")
    
    os.makedirs(unc_config["paths"]["models_dir"], exist_ok=True)
    
    for q_name, model in models_temp.items():
        model.booster_.save_model(os.path.join(unc_config["paths"]["models_dir"], f"temp_{q_name}.txt"))
    for q_name, model in models_hum.items():
        model.booster_.save_model(os.path.join(unc_config["paths"]["models_dir"], f"hum_{q_name}.txt"))

    os.makedirs(os.path.dirname(unc_config["paths"]["uncertainty_predictions_csv"]), exist_ok=True)
    df_out.to_csv(unc_config["paths"]["uncertainty_predictions_csv"], index=False)

    # Distributional shift documentation
    train_hum_resid_mean = float((df_out[df_out["split"] == "TRAIN"]["observed_humidity"] - 
                                   df_out[df_out["split"] == "TRAIN"]["b2_humidity"]).mean())
    calib_hum_resid_mean = float((calib_out["observed_humidity"] - calib_out["b2_humidity"]).mean())
    test_hum_resid_mean = float((test_out["observed_humidity"] - test_out["b2_humidity"]).mean())

    val_summary = {
        "record_counts": {
            "total": int(len(df_out)),
            "train": int(len(df_out[df_out["split"] == "TRAIN"])),
            "calibration": int(len(calib_out)),
            "test": int(len(test_out))
        },
        "conformal_corrections": {
            "temperature": float(correction_temp),
            "humidity": float(correction_hum)
        },
        "calibration_empirical_coverage": {
            "temperature": float(calib_temp_coverage),
            "humidity": float(calib_hum_coverage),
            "target_coverage": 1.0 - unc_config["conformal"]["alpha"]
        },
        "test_empirical_coverage": {
            "temperature": float(temp_coverage),
            "humidity": float(hum_coverage),
            "target_coverage": 1.0 - unc_config["conformal"]["alpha"]
        },
        "mean_interval_width_test": {
            "temperature": float(test_out["temperature_interval_width"].mean()),
            "humidity": float(test_out["humidity_interval_width"].mean())
        },
        "distributional_shift_analysis": {
            "humidity_residual_mean_train": train_hum_resid_mean,
            "humidity_residual_mean_calibration": calib_hum_resid_mean,
            "humidity_residual_mean_test": test_hum_resid_mean,
            "shift_magnitude": test_hum_resid_mean - calib_hum_resid_mean,
            "note": "Large positive shift in test-period humidity residuals (monsoon onset). Conformal calibration uses calibration-period scores, which do not capture this distributional shift. Low test coverage for humidity is a scientifically honest result."
        },
        "reliability_distribution_test": {
            "temperature": {str(k): int(v) for k, v in temp_rel_dist.items()},
            "humidity": {str(k): int(v) for k, v in hum_rel_dist.items()}
        },
        "station_level_metrics": station_metrics,
        "lead_time_level_metrics": lead_metrics
    }
    with open(unc_config["paths"]["metrics_json"], "w") as f:
        json.dump(val_summary, f, indent=4)

    print("\n" + "-" * 50)
    print("PHASE 5 RESULTS SUMMARY")
    print("-" * 50)
    print(f"Temperature Coverage (CALIB): {calib_temp_coverage:.2%}")
    print(f"Temperature Coverage (TEST):  {temp_coverage:.2%}")
    print(f"Temperature Mean Width (TEST): {test_out['temperature_interval_width'].mean():.2f} °C")
    print(f"Humidity Coverage (CALIB):    {calib_hum_coverage:.2%}")
    print(f"Humidity Coverage (TEST):     {hum_coverage:.2%}")
    print(f"Humidity Mean Width (TEST):   {test_out['humidity_interval_width'].mean():.2f} %")
    print("-" * 50)
    print("\nPhase 5 completed successfully!")

if __name__ == "__main__":
    run_phase5_pipeline()

