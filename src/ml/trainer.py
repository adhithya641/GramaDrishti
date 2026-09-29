"""
GramDrishti — Phase 4 LightGBM Residual Trainer
Trains LightGBM GBDT models on residual targets with strict hyperparameter tracking
and SHAP / gain / split feature importance calculations.
"""

from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import lightgbm as lgb
import shap


def train_residual_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cat_features: List[str],
    model_params: Dict[str, Any]
) -> lgb.LGBMRegressor:
    """
    Train a LightGBM regressor on residual targets using CPU configuration.
    """
    model = lgb.LGBMRegressor(**model_params)
    
    # Check if cat_features are present as pandas category dtype or column names
    valid_cat_features = [c for c in cat_features if c in X_train.columns]
    
    # If columns are already pandas 'category' dtype, 'auto' works natively
    if valid_cat_features and all(X_train[c].dtype.name == 'category' for c in valid_cat_features):
        cat_arg = "auto"
    elif valid_cat_features:
        cat_arg = valid_cat_features
    else:
        cat_arg = "auto"

    model.fit(
        X_train,
        y_train,
        categorical_feature=cat_arg
    )
    return model


def predict_residuals(model: lgb.LGBMRegressor, X: pd.DataFrame) -> np.ndarray:
    """
    Generate residual predictions from trained LightGBM model.
    """
    return model.predict(X)


def extract_feature_importance(
    model: lgb.LGBMRegressor,
    X_sample: pd.DataFrame,
    target_name: str
) -> pd.DataFrame:
    """
    Extract LightGBM Gain, Split, and SHAP mean absolute feature importances.
    """
    feature_names = list(X_sample.columns)
    booster = model.booster_

    gain_imp = booster.feature_importance(importance_type="gain")
    split_imp = booster.feature_importance(importance_type="split")

    # Compute SHAP values
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    if isinstance(shap_values, list):
        shap_values = np.array(shap_values[0])
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    df_imp = pd.DataFrame({
        "target": target_name,
        "feature": feature_names,
        "gain_importance": gain_imp,
        "split_importance": split_imp,
        "mean_abs_shap": mean_abs_shap
    }).sort_values(by="gain_importance", ascending=False).reset_index(drop=True)

    return df_imp
