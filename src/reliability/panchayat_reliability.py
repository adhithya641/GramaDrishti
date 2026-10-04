"""
GramDrishti — Phase 7 Panchayat Reliability Aggregator
======================================================
Aggregates 1-km grid cell predictions and reliability evaluations
to the 180 Gram Panchayats in Coimbatore District.
Preserves SUBGRID_RANGE_UNRESOLVED flag for panchayats with <3 grid cells.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from .evaluator import ReliabilityEvaluator, FreshnessEvaluator
from .fallback import FallbackHandler


class PanchayatReliabilityAggregator:
    """
    Aggregates grid cell predictions and builds panchayat-level reliability output DataFrame.
    """

    def __init__(self, config_path: Optional[str] = "configs/reliability_config.yaml"):
        self.evaluator = ReliabilityEvaluator(config_path)
        self.fallback_handler = FallbackHandler()

    def aggregate_panchayat_reliability(
        self,
        grid_predictions_df: pd.DataFrame,
        reference_time: Optional[str] = "2024-05-01 00:00:00"
    ) -> pd.DataFrame:
        """
        Input DataFrame must contain:
          - panchayat_id
          - timestamp (or observation_time)
          - lead_time (or lead_time_hours)
          - ml_temperature (or forecast_temperature)
          - ml_humidity (or forecast_humidity)
          - prob_1mm, prob_10mm, prob_25mm
          - temp_q10, temp_q90 (optional)
          - hum_q10, hum_q90 (optional)
        """
        df = grid_predictions_df.copy()

        time_col = "timestamp" if "timestamp" in df.columns else "observation_time"
        lead_col = "lead_time" if "lead_time" in df.columns else "lead_time_hours"

        df["timestamp"] = df[time_col]
        df["lead_time"] = df[lead_col]

        temp_col = "ml_temperature" if "ml_temperature" in df.columns else "forecast_temperature"
        hum_col = "ml_humidity" if "ml_humidity" in df.columns else "forecast_humidity"

        p1_col = "prob_1mm" if "prob_1mm" in df.columns else "rain_probability_1mm"
        p10_col = "prob_10mm" if "prob_10mm" in df.columns else "rain_probability_10mm"
        p25_col = "prob_25mm" if "prob_25mm" in df.columns else "rain_probability_25mm"

        records = []
        group_cols = ["panchayat_id", "timestamp", "lead_time"]
        for (gp_id, ts, lt), sub_df in df.groupby(group_cols, observed=True):
            if "grid_cell_count" in sub_df.columns:
                cell_cnt = int(sub_df["grid_cell_count"].iloc[0])
            else:
                cell_cnt = len(sub_df)

            if "aggregation_status" in sub_df.columns:
                status = str(sub_df["aggregation_status"].iloc[0])
            else:
                status = "SUBGRID_RANGE_UNRESOLVED" if cell_cnt < 3 else "OK"

            # Temperature stats
            t_vals = sub_df[temp_col].values
            t_mean = float(np.mean(t_vals))
            t_spread = float(np.std(t_vals, ddof=1)) if cell_cnt > 1 else 0.0

            if "temp_q10" in sub_df.columns and "temp_q90" in sub_df.columns:
                t_w = float(np.mean(sub_df["temp_q90"] - sub_df["temp_q10"]))
            else:
                t_w = 4.73  # Default empirical mean width from Phase 5

            # Humidity stats
            h_vals = sub_df[hum_col].values
            h_mean = float(np.mean(h_vals))
            h_spread = float(np.std(h_vals, ddof=1)) if cell_cnt > 1 else 0.0

            if "hum_q10" in sub_df.columns and "hum_q90" in sub_df.columns:
                h_w = float(np.mean(sub_df["hum_q90"] - sub_df["hum_q10"]))
            else:
                h_w = 27.61  # Default empirical mean width from Phase 5

            def safe_mean(vals):
                if vals is None:
                    return None
                clean = [v for v in vals if v is not None and not pd.isna(v)]
                return float(np.mean(clean)) if len(clean) > 0 else None

            # Rainfall stats
            p1_val = safe_mean(sub_df[p1_col].values) if p1_col in sub_df.columns else 0.112
            p10_val = safe_mean(sub_df[p10_col].values) if p10_col in sub_df.columns else None
            p25_val = safe_mean(sub_df[p25_col].values) if p25_col in sub_df.columns else None

            # Freshness evaluation
            fresh_eval = self.evaluator.freshness_evaluator.evaluate(
                timestamp=ts,
                reference_time=reference_time,
                lead_time_hours=int(lt)
            )

            # Reliability evaluations
            t_eval = self.evaluator.evaluate_temperature(t_mean, interval_width=t_w)
            h_eval = self.evaluator.evaluate_humidity(h_mean, interval_width=h_w)
            r1_eval = self.evaluator.evaluate_rainfall_threshold("1mm", p1_val, train_events=15, calib_events=9, test_events=165, temporal_shift=True)
            r10_eval = self.evaluator.evaluate_rainfall_threshold("10mm", p10_val, train_events=0, calib_events=0, test_events=6)
            r25_eval = self.evaluator.evaluate_rainfall_threshold("25mm", p25_val, train_events=0, calib_events=0, test_events=0)

            overall_eval = self.evaluator.evaluate_overall_panchayat(
                t_eval, h_eval, r1_eval, r10_eval, r25_eval, fresh_eval, grid_cell_count=cell_cnt
            )

            # Fallback evaluation for temperature
            t_fallback = self.fallback_handler.select_temperature_fallback(
                primary_pred=t_mean,
                confidence=t_eval["confidence"]
            )

            records.append({
                "panchayat_id": gp_id,
                "timestamp": str(ts),
                "lead_time": int(lt),
                "grid_cell_count": cell_cnt,
                "aggregation_status": status,
                "temperature": round(t_mean, 2),
                "temperature_spread": round(t_spread, 2),
                "temperature_interval_width": round(t_w, 2),
                "temperature_confidence": t_eval["confidence"],
                "humidity": round(h_mean, 2),
                "humidity_spread": round(h_spread, 2),
                "humidity_interval_width": round(h_w, 2),
                "humidity_confidence": h_eval["confidence"],
                "rain_probability_1mm": round(p1_val, 4) if p1_val is not None else None,
                "rain_1mm_confidence": r1_eval["confidence"],
                "rain_probability_10mm": round(p10_val, 4) if (p10_val is not None and r10_val_eval_ok(r10_eval)) else None,
                "rain_10mm_confidence": r10_eval["confidence"],
                "rain_probability_25mm": None,
                "rain_25mm_confidence": r25_eval["confidence"],
                "overall_confidence": overall_eval["overall"],
                "freshness_status": fresh_eval["status"],
                "fallback_used": t_fallback["fallback_used"],
                "fallback_source": t_fallback["source"],
                "reliability_reasons": ";".join(overall_eval["reasons"])
            })

        return pd.DataFrame(records)


def r10_val_eval_ok(r10_eval: Dict[str, Any]) -> bool:
    return r10_eval["confidence"] not in ["NOT_EVALUABLE"]
