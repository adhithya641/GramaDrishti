"""
GramDrishti — Phase 6 Rainfall Evaluator
=========================================
Calculates evaluation metrics (Brier Score, POD, FAR, CSI, Reliability)
and diagnostic breakdowns (Station, Lead Time, Monthly) for rainfall probability models.
"""

from typing import Dict, Any, List
import numpy as np
import pandas as pd


def calculate_brier_score(probs: np.ndarray, y_true: np.ndarray) -> float:
    """
    Computes Brier Score: mean squared error of probability predictions.
    BS = (1/N) * sum((p_i - y_i)^2)
    Lower is better (0.0 is perfect prediction).
    """
    p = np.array(probs, dtype=float)
    y = np.array(y_true, dtype=float)
    return float(np.mean((p - y) ** 2))


def calculate_classification_metrics(
    probs: np.ndarray,
    y_true: np.ndarray,
    threshold: float = 0.5
) -> Dict[str, float]:
    """
    Calculates POD, FAR, CSI, TP, FP, TN, FN at a decision threshold (default 0.5).
      - POD (Probability of Detection) = TP / (TP + FN)
      - FAR (False Alarm Ratio) = FP / (TP + FP)
      - CSI (Critical Success Index) = TP / (TP + FP + FN)
    """
    p_bin = (np.array(probs) >= threshold).astype(int)
    y = np.array(y_true, dtype=int)

    tp = int(np.sum((p_bin == 1) & (y == 1)))
    fp = int(np.sum((p_bin == 1) & (y == 0)))
    fn = int(np.sum((p_bin == 0) & (y == 1)))
    tn = int(np.sum((p_bin == 0) & (y == 0)))

    pod = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    far = float(fp / (tp + fp)) if (tp + fp) > 0 else 0.0
    csi = float(tp / (tp + fp + fn)) if (tp + fp + fn) > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "pod": pod,
        "far": far,
        "csi": csi
    }


def evaluate_model_performance(
    probs: np.ndarray,
    y_true: np.ndarray,
    model_name: str,
    threshold_name: str,
    split_name: str = "TEST"
) -> Dict[str, Any]:
    """
    Evaluates a single model's predictions against ground truth labels.
    """
    brier = calculate_brier_score(probs, y_true)
    clf_metrics = calculate_classification_metrics(probs, y_true, threshold=0.5)

    n = len(y_true)
    event_cnt = int(np.sum(y_true))
    pred_mean = float(np.mean(probs))
    obs_rate = float(event_cnt / n) if n > 0 else 0.0

    return {
        "model": model_name,
        "threshold": threshold_name,
        "split": split_name,
        "records": n,
        "event_count": event_cnt,
        "observed_rate": obs_rate,
        "predicted_prob_mean": pred_mean,
        "brier_score": brier,
        "pod": clf_metrics["pod"],
        "far": clf_metrics["far"],
        "csi": clf_metrics["csi"],
        "tp": clf_metrics["tp"],
        "fp": clf_metrics["fp"],
        "fn": clf_metrics["fn"],
        "tn": clf_metrics["tn"]
    }


def compute_reliability_curve(
    probs: np.ndarray,
    y_true: np.ndarray,
    n_bins: int = 5
) -> List[Dict[str, float]]:
    """
    Computes binned reliability curve statistics (mean predicted prob vs observed event rate).
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    curve_data = []

    p = np.array(probs)
    y = np.array(y_true)

    for i in range(n_bins):
        b_low, b_high = bins[i], bins[i+1]
        mask = (p >= b_low) & (p <= b_high) if i == n_bins - 1 else (p >= b_low) & (p < b_high)
        sub_cnt = int(np.sum(mask))

        if sub_cnt > 0:
            sub_pred_mean = float(np.mean(p[mask]))
            sub_obs_rate = float(np.mean(y[mask]))
        else:
            sub_pred_mean = float((b_low + b_high) / 2.0)
            sub_obs_rate = 0.0

        curve_data.append({
            "bin_lower": float(b_low),
            "bin_upper": float(b_high),
            "count": sub_cnt,
            "mean_pred_prob": sub_pred_mean,
            "mean_observed_rate": sub_obs_rate
        })

    return curve_data


def analyze_station_performance(
    test_df: pd.DataFrame,
    probs_dict: Dict[str, np.ndarray],
    targets: List[str]
) -> pd.DataFrame:
    """
    Computes station-level performance for R2 Calibrated model on TEST set.
    """
    records = []
    stations = sorted(test_df["station_id"].unique())

    for target in targets:
        probs = probs_dict[target]
        y_true = test_df[target].values

        for stn in stations:
            mask = (test_df["station_id"] == stn).values
            n_stn = int(np.sum(mask))

            if n_stn == 0:
                continue

            sub_p = probs[mask]
            sub_y = y_true[mask]

            brier = calculate_brier_score(sub_p, sub_y)
            clf = calculate_classification_metrics(sub_p, sub_y)

            records.append({
                "station_id": stn,
                "target": target,
                "records": n_stn,
                "event_count": int(np.sum(sub_y)),
                "observed_rate": float(np.mean(sub_y)),
                "predicted_prob_mean": float(np.mean(sub_p)),
                "brier_score": brier,
                "pod": clf["pod"],
                "far": clf["far"],
                "csi": clf["csi"]
            })

    return pd.DataFrame(records)


def analyze_lead_time_performance(
    test_df: pd.DataFrame,
    probs_dict: Dict[str, np.ndarray],
    targets: List[str]
) -> pd.DataFrame:
    """
    Computes lead-time performance for R2 Calibrated model on TEST set.
    """
    records = []
    lead_times = sorted(test_df["lead_time_hours"].unique())

    for target in targets:
        probs = probs_dict[target]
        y_true = test_df[target].values

        for lt in lead_times:
            mask = (test_df["lead_time_hours"] == lt).values
            n_lt = int(np.sum(mask))

            if n_lt == 0:
                continue

            sub_p = probs[mask]
            sub_y = y_true[mask]

            brier = calculate_brier_score(sub_p, sub_y)
            clf = calculate_classification_metrics(sub_p, sub_y)

            records.append({
                "lead_time_hours": int(lt),
                "target": target,
                "records": n_lt,
                "event_count": int(np.sum(sub_y)),
                "observed_rate": float(np.mean(sub_y)),
                "predicted_prob_mean": float(np.mean(sub_p)),
                "brier_score": brier,
                "pod": clf["pod"],
                "far": clf["far"],
                "csi": clf["csi"]
            })

    return pd.DataFrame(records)


def analyze_monthly_performance(
    test_df: pd.DataFrame,
    probs_dict: Dict[str, np.ndarray],
    targets: List[str]
) -> pd.DataFrame:
    """
    Computes monthly (May vs June) performance for R2 Calibrated model on TEST set.
    """
    records = []
    obs_times = pd.to_datetime(test_df["observation_time"])
    months = [5, 6]

    for target in targets:
        probs = probs_dict[target]
        y_true = test_df[target].values

        for m in months:
            mask = (obs_times.dt.month == m).values
            n_m = int(np.sum(mask))

            if n_m == 0:
                continue

            sub_p = probs[mask]
            sub_y = y_true[mask]

            brier = calculate_brier_score(sub_p, sub_y)
            clf = calculate_classification_metrics(sub_p, sub_y)
            m_name = "May" if m == 5 else "June"

            records.append({
                "month_name": m_name,
                "month": m,
                "target": target,
                "records": n_m,
                "event_count": int(np.sum(sub_y)),
                "observed_rate": float(np.mean(sub_y)),
                "predicted_prob_mean": float(np.mean(sub_p)),
                "brier_score": brier,
                "pod": clf["pod"],
                "far": clf["far"],
                "csi": clf["csi"]
            })

    return pd.DataFrame(records)
