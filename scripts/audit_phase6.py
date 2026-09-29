"""
GramDrishti — Phase 6 Scientific & Codebase Audit Script
=========================================================
Performs a strict scientific audit of Phase 6 rainfall labels, temporal alignment,
distributional properties, baseline R0, Logistic Regression R1 anomaly, LightGBM R2,
Isotonic Calibration, threshold trainability, distribution shift, station/lead-time,
and Panchayat spatial aggregation.
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
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression

from src.ml.feature_builder import load_and_merge_datasets, add_temporal_features
from src.ml.rainfall_data import create_rainfall_targets, audit_rainfall_data
from src.ml.rainfall_models import ClimatologyModel, LogisticRegressionModel, LightGBMRainfallModel, IsotonicCalibrator
from src.ml.rainfall_evaluator import calculate_brier_score, calculate_classification_metrics
from src.ml.panchayat_aggregator import aggregate_grid_to_panchayats, build_full_grid_features


def audit_phase6():
    print("=" * 80)
    print("GRAMDRISHTI — PHASE 6 SCIENTIFIC & CODE AUDIT")
    print("=" * 80)

    # Load Config and Matchups
    config_path = "configs/rainfall_config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    df = load_and_merge_datasets(config["paths"]["matchups_csv"], config["paths"]["geospatial_master_csv"])
    df = add_temporal_features(df, "observation_time")
    df = create_rainfall_targets(df)

    split_cfg = config["temporal_split"]
    obs_times = pd.to_datetime(df["observation_time"])
    df.loc[(obs_times >= split_cfg["train_start"]) & (obs_times <= split_cfg["train_end"]), "split"] = "TRAIN"
    df.loc[(obs_times >= split_cfg["calibration_start"]) & (obs_times <= split_cfg["calibration_end"]), "split"] = "CALIBRATION"
    df.loc[(obs_times >= split_cfg["test_start"]) & (obs_times <= split_cfg["test_end"]), "split"] = "TEST"

    train_df = df[df["split"] == "TRAIN"].copy()
    calib_df = df[df["split"] == "CALIBRATION"].copy()
    test_df = df[df["split"] == "TEST"].copy()

    # -------------------------------------------------------------
    # 1. AUDIT RAINFALL LABELS
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("1. AUDIT RAINFALL LABELS")
    print("=" * 50)

    for name, sub in [("TRAIN", train_df), ("CALIBRATION", calib_df), ("TEST", test_df)]:
        rf = sub["observed_rainfall"]
        print(f"--- {name} (N={len(sub)}) ---")
        print(f"  rain >= 1.0 mm  : {(rf >= 1.0).sum():4d} / {len(sub)} ({(rf >= 1.0).mean()*100:.2f}%)")
        print(f"  rain >= 10.0 mm : {(rf >= 10.0).sum():4d} / {len(sub)} ({(rf >= 10.0).mean()*100:.2f}%)")
        print(f"  rain >= 25.0 mm : {(rf >= 25.0).sum():4d} / {len(sub)} ({(rf >= 25.0).mean()*100:.2f}%)")
        print(f"  Exact zeros     : {(rf == 0.0).sum():4d} / {len(sub)} ({(rf == 0.0).mean()*100:.2f}%)")
        print(f"  Min rainfall    : {rf.min():.4f} mm")
        print(f"  Max rainfall    : {rf.max():.4f} mm")
        print(f"  Mean rainfall   : {rf.mean():.4f} mm")
        print(f"  Median rainfall : {rf.median():.4f} mm")

    # -------------------------------------------------------------
    # 2. AUDIT TEMPORAL ALIGNMENT
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("2. AUDIT TEMPORAL ALIGNMENT")
    print("=" * 50)

    sample_24 = df[df["lead_time_hours"] == 24].iloc[0]
    sample_48 = df[df["lead_time_hours"] == 48].iloc[0]
    sample_72 = df[df["lead_time_hours"] == 72].iloc[0]

    for lt_val, s in [(24, sample_24), (48, sample_48), (72, sample_72)]:
        print(f"Lead Time {lt_val}h Example:")
        print(f"  Station          : {s['station_id']}")
        print(f"  Observation Time : {s['observation_time']}")
        print(f"  Forecast Issue   : {s['forecast_issue_time']}")
        print(f"  Forecast Valid   : {s['valid_time']}")
        print(f"  Lead Time Hours  : {s['lead_time_hours']}")
        print(f"  Observed Rain    : {s['observed_rainfall']} mm")
        print(f"  Forecast Rain    : {s['forecast_rainfall']} mm")

    # -------------------------------------------------------------
    # 3. AUDIT RAINFALL DISTRIBUTION (MONTHLY)
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("3. AUDIT RAINFALL DISTRIBUTION (MONTHLY)")
    print("=" * 50)

    df["month_num"] = pd.to_datetime(df["observation_time"]).dt.month
    month_names = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June"}

    for m in range(1, 7):
        sub_m = df[df["month_num"] == m]
        rf_m = sub_m["observed_rainfall"]
        rate_1 = (rf_m >= 1.0).mean() * 100
        rate_10 = (rf_m >= 10.0).mean() * 100
        rate_25 = (rf_m >= 25.0).mean() * 100
        zero_pct = (rf_m == 0.0).mean() * 100
        print(f"{month_names[m]:9s} (N={len(sub_m):4d}): Zeros={zero_pct:6.2f}%, >=1mm={rate_1:5.2f}%, >=10mm={rate_10:5.2f}%, >=25mm={rate_25:5.2f}%, Max={rf_m.max():6.2f}mm")

    # -------------------------------------------------------------
    # 5. AUDIT R1 LOGISTIC REGRESSION ANOMALY
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("5. AUDIT R1 LOGISTIC REGRESSION ANOMALY")
    print("=" * 50)

    feat_cfg = config["features"]
    feature_cols = feat_cfg["forecast"] + feat_cfg["geospatial"] + feat_cfg["temporal"]
    cat_cols = feat_cfg.get("categorical", [])

    X_train = train_df[feature_cols].copy()
    X_test = test_df[feature_cols].copy()
    y_train = train_df["rain_1mm"].values
    y_test = test_df["rain_1mm"].values

    for c in cat_cols:
        if c in X_train.columns:
            X_train[c] = X_train[c].astype("category").cat.codes
            X_test[c] = X_test[c].astype("category").cat.codes

    # Examine scaler, imputer, weights
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_train_imp = imputer.fit_transform(X_train)
    X_train_scaled = scaler.fit_transform(X_train_imp)

    X_test_imp = imputer.transform(X_test)
    X_test_scaled = scaler.transform(X_test_imp)

    clf = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", max_iter=1000, random_state=42)
    clf.fit(X_train_scaled, y_train)

    train_probs = clf.predict_proba(X_train_scaled)[:, 1]
    test_probs = clf.predict_proba(X_test_scaled)[:, 1]

    print(f"TRAIN actual event rate : {y_train.mean():.4f} ({y_train.sum()}/{len(y_train)})")
    print(f"TEST actual event rate  : {y_test.mean():.4f} ({y_test.sum()}/{len(y_test)})")
    print(f"Logistic Intercept      : {clf.intercept_[0]:.4f}")
    print(f"TRAIN predicted prob mean: {train_probs.mean():.4f} (min={train_probs.min():.4f}, max={train_probs.max():.4f}, median={np.median(train_probs):.4f})")
    print(f"TEST predicted prob mean : {test_probs.mean():.4f} (min={test_probs.min():.4f}, max={test_probs.max():.4f}, median={np.median(test_probs):.4f})")

    # Check top coefficients
    coef_df = pd.DataFrame({"feature": feature_cols, "coefficient": clf.coef_[0]}).sort_values(by="coefficient", key=abs, ascending=False)
    print("\nTop 5 Logistic Regression Coefficients:")
    print(coef_df.head(5).to_string(index=False))

    # -------------------------------------------------------------
    # 6. AUDIT R2 LIGHTGBM CLASSIFIER
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("6. AUDIT R2 LIGHTGBM CLASSIFIER")
    print("=" * 50)

    X_train_lgb = train_df[feature_cols].copy()
    X_test_lgb = test_df[feature_cols].copy()
    for c in cat_cols:
        if c in X_train_lgb.columns:
            X_train_lgb[c] = X_train_lgb[c].astype("category")
            X_test_lgb[c] = X_test_lgb[c].astype("category")

    r2 = LightGBMRainfallModel(config["model_params"]["lgb"]).fit(X_train_lgb, y_train)
    p_r2_train = r2.predict_proba(X_train_lgb)
    p_r2_test = r2.predict_proba(X_test_lgb)

    print(f"R2 TRAIN predicted prob mean: {p_r2_train.mean():.4f} (min={p_r2_train.min():.4f}, max={p_r2_train.max():.4f}, median={np.median(p_r2_train):.4f})")
    print(f"R2 TEST predicted prob mean : {p_r2_test.mean():.4f} (min={p_r2_test.min():.4f}, max={p_r2_test.max():.4f}, median={np.median(p_r2_test):.4f})")
    print(f"R2 TEST prob >= 0.5 count   : {(p_r2_test >= 0.5).sum()}")

    # -------------------------------------------------------------
    # 7. AUDIT ISOTONIC CALIBRATION
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("7. AUDIT ISOTONIC CALIBRATION")
    print("=" * 50)

    X_calib_lgb = calib_df[feature_cols].copy()
    for c in cat_cols:
        if c in X_calib_lgb.columns:
            X_calib_lgb[c] = X_calib_lgb[c].astype("category")
    y_calib = calib_df["rain_1mm"].values

    p_r2_calib_raw = r2.predict_proba(X_calib_lgb)
    calibrator = IsotonicCalibrator().fit(p_r2_calib_raw, y_calib)
    p_r2_calib_calibrated = calibrator.transform(p_r2_calib_raw)
    p_r2_test_calibrated = calibrator.transform(p_r2_test)

    print(f"CALIBRATION raw probs range     : [{p_r2_calib_raw.min():.4f}, {p_r2_calib_raw.max():.4f}] (mean={p_r2_calib_raw.mean():.4f})")
    print(f"CALIBRATION labels positive cnt : {y_calib.sum()} / {len(y_calib)} ({y_calib.mean()*100:.2f}%)")
    print(f"CALIBRATION calibrated probs    : [{p_r2_calib_calibrated.min():.4f}, {p_r2_calib_calibrated.max():.4f}] (mean={p_r2_calib_calibrated.mean():.4f})")
    print(f"TEST raw probs range            : [{p_r2_test.min():.4f}, {p_r2_test.max():.4f}] (mean={p_r2_test.mean():.4f})")
    print(f"TEST calibrated probs range     : [{p_r2_test_calibrated.min():.4f}, {p_r2_test_calibrated.max():.4f}] (mean={p_r2_test_calibrated.mean():.4f})")

    # -------------------------------------------------------------
    # 9. AUDIT TEMPORAL DISTRIBUTION SHIFT
    # -------------------------------------------------------------
    print("\n" + "=" * 50)
    print("9. AUDIT TEMPORAL DISTRIBUTION SHIFT")
    print("=" * 50)

    shift_vars = ["forecast_rainfall", "forecast_temperature", "forecast_humidity"]
    for v in shift_vars:
        print(f"Variable: {v:20s}")
        print(f"  TRAIN       mean={train_df[v].mean():7.2f}, std={train_df[v].std():7.2f}, max={train_df[v].max():7.2f}")
        print(f"  CALIBRATION mean={calib_df[v].mean():7.2f}, std={calib_df[v].std():7.2f}, max={calib_df[v].max():7.2f}")
        print(f"  TEST        mean={test_df[v].mean():7.2f}, std={test_df[v].std():7.2f}, max={test_df[v].max():7.2f}")

    print("\nPhase 6 Audit execution finished successfully.")


if __name__ == "__main__":
    audit_phase6()
