"""
GramDrishti — Phase 5 Conformal Calibration
Applies Conformalized Quantile Regression (CQR) correction.
"""
import numpy as np
import pandas as pd

def compute_conformal_scores(
    y_calib: pd.Series,
    q10_calib: pd.Series,
    q90_calib: pd.Series
) -> np.ndarray:
    """
    Compute conformal non-conformity scores on calibration set.
    Score E_i = max(q10_i - y_i, y_i - q90_i)
    """
    scores = np.maximum(
        q10_calib - y_calib,
        y_calib - q90_calib
    )
    return np.asarray(scores)

def get_conformal_correction(scores: np.ndarray, alpha: float) -> float:
    """
    Compute the empirical quantile of the scores.
    """
    n = len(scores)
    # The CQR conformal threshold
    q = (1 - alpha) * (1 + 1 / n)
    if q > 1.0:
        q = 1.0
    return float(np.quantile(scores, q, method='higher'))

def apply_conformal_correction(
    q10_preds: pd.Series,
    q90_preds: pd.Series,
    correction: float
) -> pd.DataFrame:
    """
    Apply conformal correction to test predictions.
    q10_new = q10 - correction
    q90_new = q90 + correction
    """
    return pd.DataFrame({
        'q10_calibrated': q10_preds - correction,
        'q90_calibrated': q90_preds + correction
    })

def classify_reliability(
    interval_width: pd.Series,
    medium_threshold: float,
    low_threshold: float
) -> pd.Series:
    """Classify the uncertainty interval width into HIGH, MEDIUM, LOW reliability."""
    conditions = [
        interval_width > low_threshold,
        interval_width > medium_threshold
    ]
    choices = ['LOW', 'MEDIUM']
    # If the width is <= medium_threshold, it's HIGH reliability
    return pd.Series(np.select(conditions, choices, default='HIGH'), index=interval_width.index)
