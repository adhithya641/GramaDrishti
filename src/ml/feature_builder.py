"""
GramDrishti — Phase 4 Feature Builder
Joins weather matchup dataset with geospatial terrain/landcover features
and constructs legitimate forecast-time features while enforcing strict leakage guards.
"""

from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd
import yaml


def load_and_merge_datasets(
    matchups_path: str,
    geospatial_path: str
) -> pd.DataFrame:
    """
    Load matchups and geospatial master feature tables and merge on grid_id.
    Prevents column conflicts by selectively keeping geospatial features.
    """
    matchups_df = pd.read_csv(matchups_path)
    geo_df = pd.read_csv(geospatial_path)

    # Columns in geo_df to drop if already in matchups_df (except grid_id)
    overlapping_cols = [c for c in geo_df.columns if c in matchups_df.columns and c != "grid_id"]
    geo_features_df = geo_df.drop(columns=overlapping_cols)

    # Merge on grid_id
    merged_df = matchups_df.merge(geo_features_df, on="grid_id", how="left")
    return merged_df


def add_temporal_features(df: pd.DataFrame, time_col: str = "observation_time") -> pd.DataFrame:
    """
    Derive cyclical day-of-year and month features from observation_time.
    """
    df = df.copy()
    times = pd.to_datetime(df[time_col])
    day_of_year = times.dt.dayofyear

    df["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    df["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    df["month"] = times.dt.month
    return df


def prepare_features_and_targets(
    df: pd.DataFrame,
    config: Dict[str, Any],
    target_type: str = "temperature"
) -> Tuple[pd.DataFrame, pd.Series, List[str], List[str]]:
    """
    Prepares feature DataFrame (X), target Series (y), feature column list,
    and categorical column names for LightGBM.
    Enforces strict leakage guards.
    """
    target_info = config["targets"][target_type]
    baseline_col = target_info["baseline_col"]
    obs_col = target_info["observation_col"]
    residual_col = target_info["residual_col"]

    # Calculate residual target if not present
    if residual_col not in df.columns:
        df[residual_col] = df[obs_col] - df[baseline_col]

    # Collect candidate feature column names
    feat_cfg = config["features"]
    forecast_feats = feat_cfg["forecast"]
    geo_feats = feat_cfg["geospatial"]
    temp_feats = feat_cfg["temporal"]
    cat_feats = feat_cfg.get("categorical", [])

    baseline_feat = [baseline_col]

    feature_cols = forecast_feats + baseline_feat + geo_feats + temp_feats

    # Validate leakage
    validate_feature_leakage(feature_cols, config["strictly_forbidden_features"])

    # Prepare X and y
    X = df[feature_cols].copy()
    y = df[residual_col].copy()

    # Format categorical columns as pandas Categorical
    for cat in cat_feats:
        if cat in X.columns:
            X[cat] = X[cat].astype("category")

    return X, y, feature_cols, cat_feats


def validate_feature_leakage(feature_cols: List[str], forbidden_cols: List[str]) -> None:
    """
    Ensure no forbidden column or leakage variable exists in feature list.
    Raises ValueError if target leakage is detected.
    """
    leakage_found = [c for c in feature_cols if c in forbidden_cols]
    if leakage_found:
        raise ValueError(
            f"CRITICAL TARGET LEAKAGE DETECTED! Forbidden features present in matrix: {leakage_found}"
        )
