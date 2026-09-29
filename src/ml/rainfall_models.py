"""
GramDrishti — Phase 6 Rainfall Probability Models
===================================================
Implements:
  - R0: Climatology Baseline Model
  - R1: Logistic Regression Baseline Model
  - R2 Raw: LightGBM Binary Classifier Model
  - R2 Calibrated: Isotonic Regression Post-Processing
"""

from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
import lightgbm as lgb


class ClimatologyModel:
    """
    R0 Baseline: Constant climatological probability fit on TRAIN set.
    """
    def __init__(self):
        self.prior_probability: float = 0.0

    def fit(self, y_train: pd.Series | np.ndarray) -> "ClimatologyModel":
        y = np.array(y_train)
        self.prior_probability = float(np.mean(y)) if len(y) > 0 else 0.0
        return self

    def predict_proba(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        n = len(X)
        return np.full(n, self.prior_probability, dtype=float)


class LogisticRegressionModel:
    """
    R1 Baseline: Logistic Regression using forecast & geospatial features.
    Handles single-class targets gracefully.
    """
    def __init__(self, config_params: Optional[Dict[str, Any]] = None):
        params = config_params or {"penalty": "l2", "C": 1.0, "solver": "lbfgs", "max_iter": 1000, "random_state": 42}
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(strategy="median")
        self.model = LogisticRegression(**params)
        self.single_class_val: Optional[float] = None
        self.feature_names: list = []

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series | np.ndarray) -> "LogisticRegressionModel":
        y = np.array(y_train)
        self.feature_names = list(X_train.columns)
        unique_classes = np.unique(y)

        if len(unique_classes) < 2:
            self.single_class_val = float(unique_classes[0])
            return self

        self.single_class_val = None
        # Convert categoricals to numeric codes for logistic regression
        X_num = X_train.copy()
        for col in X_num.columns:
            if X_num[col].dtype.name == "category" or X_num[col].dtype == object:
                X_num[col] = X_num[col].astype("category").cat.codes

        X_imp = self.imputer.fit_transform(X_num)
        X_scaled = self.scaler.fit_transform(X_imp)
        self.model.fit(X_scaled, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n = len(X)
        if self.single_class_val is not None:
            return np.full(n, self.single_class_val, dtype=float)

        X_num = X.copy()
        for col in X_num.columns:
            if X_num[col].dtype.name == "category" or X_num[col].dtype == object:
                X_num[col] = X_num[col].astype("category").cat.codes

        X_imp = self.imputer.transform(X_num)
        X_scaled = self.scaler.transform(X_imp)
        probs = self.model.predict_proba(X_scaled)[:, 1]
        return np.clip(probs, 0.0, 1.0)


class LightGBMRainfallModel:
    """
    R2 Model: LightGBM Binary Classifier for rainfall probability estimation.
    Handles single-class targets gracefully.
    """
    def __init__(self, config_params: Optional[Dict[str, Any]] = None):
        params = config_params or {
            "objective": "binary", "metric": "binary_logloss",
            "learning_rate": 0.05, "n_estimators": 100, "max_depth": 4,
            "num_leaves": 12, "min_child_samples": 10, "subsample": 0.8,
            "colsample_bytree": 0.8, "random_state": 42, "n_jobs": -1, "verbose": -1
        }
        self.params = params
        self.model: Optional[lgb.LGBMClassifier] = None
        self.single_class_val: Optional[float] = None
        self.feature_names: list = []

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series | np.ndarray) -> "LightGBMRainfallModel":
        y = np.array(y_train)
        self.feature_names = list(X_train.columns)
        unique_classes = np.unique(y)

        if len(unique_classes) < 2:
            self.single_class_val = float(unique_classes[0])
            return self

        self.single_class_val = None
        self.model = lgb.LGBMClassifier(**self.params)
        self.model.fit(X_train, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        n = len(X)
        if self.single_class_val is not None:
            return np.full(n, self.single_class_val, dtype=float)

        probs = self.model.predict_proba(X)[:, 1]
        return np.clip(probs, 0.0, 1.0)


class IsotonicCalibrator:
    """
    Isotonic Regression probability calibrator.
    Fitted ONLY on CALIBRATION set predictions and labels.
    """
    def __init__(self):
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.is_single_class: bool = False
        self.constant_val: float = 0.0

    def fit(self, raw_probs_calib: np.ndarray, y_calib: pd.Series | np.ndarray) -> "IsotonicCalibrator":
        y = np.array(y_calib, dtype=float)
        p = np.array(raw_probs_calib, dtype=float)

        unique_y = np.unique(y)
        if len(unique_y) < 2:
            self.is_single_class = True
            self.constant_val = float(unique_y[0])
            return self

        self.is_single_class = False
        self.calibrator.fit(p, y)
        return self

    def transform(self, raw_probs: np.ndarray) -> np.ndarray:
        n = len(raw_probs)
        if self.is_single_class:
            return np.full(n, self.constant_val, dtype=float)

        p_calib = self.calibrator.transform(raw_probs)
        return np.clip(p_calib, 0.0, 1.0)
