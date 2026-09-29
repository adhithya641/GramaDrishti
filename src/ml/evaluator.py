"""
GramDrishti — Phase 4 Model Evaluator
Computes MAE, RMSE, and Bias for baselines (B0-B3) and ML models across temporal splits,
executes ablation tests (Forecast+Time vs Full Geospatial), and computes station-wise skill.
"""

from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import lightgbm as lgb
from src.ml.trainer import train_residual_model, predict_residuals


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Calculate MAE, RMSE, and Bias (mean(pred - true)).
    """
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    bias = float(np.mean(errors))
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "bias": round(bias, 4)
    }


def calculate_improvement(baseline_mae: float, ml_mae: float) -> float:
    """
    Compute percentage improvement of ML MAE over baseline MAE:
    improvement = 100 * (baseline_mae - ml_mae) / baseline_mae
    Positive means ML improved; negative means ML was worse.
    """
    if baseline_mae == 0:
        return 0.0
    imp = 100.0 * (baseline_mae - ml_mae) / baseline_mae
    return round(imp, 2)


def evaluate_all_baselines_and_ml(
    df: pd.DataFrame,
    target_var: str = "temperature"
) -> pd.DataFrame:
    """
    Calculate MAE, RMSE, Bias for B0, B1, B2, B3, and ML model across available splits.
    """
    obs_col = f"observed_{target_var}"
    models = {
        "B0": f"b0_{target_var}",
        "B1": f"b1_{target_var}",
        "B2": f"b2_{target_var}",
        "B3": f"b3_{target_var}",
        "ML": f"ml_{target_var}"
    }

    records = []
    splits = df["split"].unique()

    for split in splits:
        split_df = df[df["split"] == split]
        y_true = split_df[obs_col].values

        for m_name, m_col in models.items():
            if m_col in split_df.columns:
                y_pred = split_df[m_col].values
                metrics = calculate_metrics(y_true, y_pred)
                records.append({
                    "target": target_var,
                    "split": split,
                    "model": m_name,
                    "record_count": len(split_df),
                    "mae": metrics["mae"],
                    "rmse": metrics["rmse"],
                    "bias": metrics["bias"]
                })

    return pd.DataFrame(records)


def run_ablation_study(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    config: Dict[str, Any],
    target_type: str = "temperature"
) -> pd.DataFrame:
    """
    Perform ablation comparison on TEST split:
    Model A: Forecast + temporal features only
    Model B: Full Model (Forecast + temporal + terrain/GIS features)
    """
    target_info = config["targets"][target_type]
    baseline_col = target_info["baseline_col"]
    obs_col = target_info["observation_col"]
    residual_col = target_info["residual_col"]
    model_params = config["model_params"]

    # Target calculation
    y_train = train_df[obs_col] - train_df[baseline_col]
    y_test_obs = test_df[obs_col].values
    b2_test = test_df[baseline_col].values

    # Feature sets (Standardized ordering: forecast -> baseline -> geospatial -> temporal)
    forecast_feats = config["features"]["forecast"]
    temp_feats = config["features"]["temporal"]
    geo_feats = config["features"]["geospatial"]
    cat_feats = config["features"].get("categorical", [])

    feats_model_a = forecast_feats + [baseline_col] + temp_feats
    feats_model_b = forecast_feats + [baseline_col] + geo_feats + temp_feats

    # Model A: Forecast + Time
    X_train_a = train_df[feats_model_a].copy()
    X_test_a = test_df[feats_model_a].copy()
    model_a = train_residual_model(X_train_a, y_train, [], model_params)
    pred_res_a = predict_residuals(model_a, X_test_a)
    ml_pred_a = b2_test + pred_res_a
    metrics_a = calculate_metrics(y_test_obs, ml_pred_a)

    # Model B: Full Model (Forecast + Time + GIS)
    X_train_b = train_df[feats_model_b].copy()
    X_test_b = test_df[feats_model_b].copy()
    for cat in cat_feats:
        if cat in X_train_b.columns:
            X_train_b[cat] = X_train_b[cat].astype("category")
            X_test_b[cat] = X_test_b[cat].astype("category")

    model_b = train_residual_model(X_train_b, y_train, cat_feats, model_params)
    pred_res_b = predict_residuals(model_b, X_test_b)
    ml_pred_b = b2_test + pred_res_b
    metrics_b = calculate_metrics(y_test_obs, ml_pred_b)

    ablation_results = [
        {
            "target": target_type,
            "ablation_setting": "Model A (Forecast + Time Only)",
            "feature_count": len(feats_model_a),
            "mae": metrics_a["mae"],
            "rmse": metrics_a["rmse"],
            "bias": metrics_a["bias"]
        },
        {
            "target": target_type,
            "ablation_setting": "Model B (Full Forecast + Time + Terrain/GIS)",
            "feature_count": len(feats_model_b),
            "mae": metrics_b["mae"],
            "rmse": metrics_b["rmse"],
            "bias": metrics_b["bias"]
        }
    ]

    return pd.DataFrame(ablation_results)


def station_group_analysis(
    test_df: pd.DataFrame,
    target_type: str = "temperature"
) -> pd.DataFrame:
    """
    Calculate TEST metrics per station: station_id, station elevation,
    elevation group, record count, B2 MAE, B3 MAE, ML MAE.
    """
    obs_col = f"observed_{target_type}"
    b2_col = f"b2_{target_type}"
    b3_col = f"b3_{target_type}"
    ml_col = f"ml_{target_type}"

    stations = sorted(test_df["station_id"].unique())
    records = []

    for stn in stations:
        stn_df = test_df[test_df["station_id"] == stn]
        y_true = stn_df[obs_col].values

        b2_pred = stn_df[b2_col].values
        b3_pred = stn_df[b3_col].values
        ml_pred = stn_df[ml_col].values

        stn_elevation = float(stn_df["station_elevation"].iloc[0])
        elev_group = "HIGH (>500m)" if stn_elevation > 500 else "LOW (<=500m)"

        b2_mae = calculate_metrics(y_true, b2_pred)["mae"]
        b3_mae = calculate_metrics(y_true, b3_pred)["mae"]
        ml_mae = calculate_metrics(y_true, ml_pred)["mae"]

        imp_vs_b2 = calculate_improvement(b2_mae, ml_mae)
        imp_vs_b3 = calculate_improvement(b3_mae, ml_mae)

        records.append({
            "target": target_type,
            "station_id": stn,
            "station_elevation": stn_elevation,
            "elevation_group": elev_group,
            "record_count": len(stn_df),
            "b2_mae": b2_mae,
            "b3_mae": b3_mae,
            "ml_mae": ml_mae,
            "ml_vs_b2_imp_pct": imp_vs_b2,
            "ml_vs_b3_imp_pct": imp_vs_b3
        })

    return pd.DataFrame(records)
