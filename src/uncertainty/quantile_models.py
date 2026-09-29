"""
GramDrishti — Phase 5 Quantile Models
Trains separate LightGBM models for q10, q50, q90 to predict residuals.
Ensures monotonic ordering.
"""
from typing import Dict, Any, List
import numpy as np
import pandas as pd
import lightgbm as lgb

def train_quantile_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cat_features: List[str],
    quantile: float,
    model_params: Dict[str, Any]
) -> lgb.LGBMRegressor:
    """Train a single LightGBM quantile regression model."""
    params = model_params.copy()
    params['objective'] = 'quantile'
    params['alpha'] = quantile

    model = lgb.LGBMRegressor(**params)
    
    valid_cat_features = [c for c in cat_features if c in X_train.columns]
    
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

def predict_quantiles(
    models: Dict[str, lgb.LGBMRegressor],
    X: pd.DataFrame
) -> pd.DataFrame:
    """Generate predictions for all quantiles and enforce monotonic ordering."""
    preds = {}
    for q_name, model in models.items():
        preds[q_name] = model.predict(X)
    
    df_preds = pd.DataFrame(preds)
    
    # Enforce q10 <= q50 <= q90 using monotonic rearrangement (sorting or max/min)
    # Simple enforcement:
    df_preds['median'] = np.maximum(df_preds['lower'], df_preds['median'])
    df_preds['upper'] = np.maximum(df_preds['median'], df_preds['upper'])
    
    return df_preds
