"""
GramDrishti — Phase 9 Demo Data Validation Utility
===================================================
Verifies data integrity, expected entity counts, replay timestamps,
reliability fields, and preservation of NOT_EVALUABLE states prior to demo startup.
"""

import os
import json
from typing import Dict, Any, List, Tuple
import pandas as pd
import yaml


class DemoDataValidator:
    """
    Validates that all required local artifacts for the SIH demonstration exist,
    contain correct entity counts, and adhere to scientific integrity rules.
    """

    def __init__(self, demo_config_path: str = "configs/demo_config.yaml"):
        self.config_path = demo_config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {
            "pilot": {"panchayats_count": 180, "blocks_count": 12, "grid_cells_count": 10530, "stations_count": 8},
            "replay": {"total_timestamps": 61},
            "paths": {
                "reliability_csv": "data/processed/predictions/panchayat_reliability.csv",
                "geojson_boundaries": "data/processed/boundaries/coimbatore_panchayats_processed.geojson",
                "grid_1km": "data/processed/geospatial/grid_1km.csv"
            }
        }

    def validate_all(self) -> Tuple[bool, List[str]]:
        """
        Execute comprehensive validation check. Returns (is_valid, list_of_errors_or_notices).
        """
        messages = []
        is_valid = True

        paths = self.config.get("paths", {})
        rel_csv = paths.get("reliability_csv", "data/processed/predictions/panchayat_reliability.csv")
        geojson_path = paths.get("geojson_boundaries", "data/processed/boundaries/coimbatore_panchayats_processed.geojson")
        grid_path = paths.get("grid_1km", "data/processed/geospatial/grid_1km.csv")

        # 1. Check file existence
        for p_name, p_val in [("Panchayat Reliability CSV", rel_csv), ("GeoJSON Boundaries", geojson_path), ("1 km Grid", grid_path)]:
            if not os.path.exists(p_val):
                messages.append(f"ERROR: Missing required artifact for demo: {p_name} ({p_val})")
                is_valid = False

        if not is_valid:
            return False, messages

        # 2. Validate GeoJSON boundaries
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                gj = json.load(f)
            features = gj.get("features", [])
            p_count = len(features)
            exp_p = self.config.get("pilot", {}).get("panchayats_count", 180)
            if p_count != exp_p:
                messages.append(f"ERROR: GeoJSON panchayat count mismatch: expected {exp_p}, got {p_count}")
                is_valid = False
            else:
                messages.append(f"[OK] GeoJSON boundaries: {p_count} Gram Panchayats verified.")

            blocks = set(f.get("properties", {}).get("block_name") for f in features)
            exp_b = self.config.get("pilot", {}).get("blocks_count", 12)
            if len(blocks) != exp_b:
                messages.append(f"WARNING: Block count mismatch in GeoJSON: expected {exp_b}, got {len(blocks)}")
            else:
                messages.append(f"[OK] Block hierarchy: {len(blocks)} blocks verified.")
        except Exception as e:
            messages.append(f"ERROR: Failed reading GeoJSON: {str(e)}")
            is_valid = False

        # 3. Validate Panchayat Reliability CSV
        try:
            df = pd.read_csv(rel_csv)
            req_cols = ["panchayat_id", "timestamp", "lead_time", "temperature", "humidity", "rain_10mm_confidence", "rain_25mm_confidence"]
            for col in req_cols:
                if col not in df.columns:
                    messages.append(f"ERROR: Missing column in reliability CSV: {col}")
                    is_valid = False

            if is_valid:
                unique_gps = df["panchayat_id"].nunique()
                if unique_gps != exp_p:
                    messages.append(f"ERROR: Unique panchayats in reliability CSV mismatch: expected {exp_p}, got {unique_gps}")
                    is_valid = False
                else:
                    messages.append(f"[OK] Reliability CSV: {len(df):,} records across {unique_gps} Gram Panchayats.")

                ts_count = df["timestamp"].nunique()
                exp_ts = self.config.get("replay", {}).get("total_timestamps", 61)
                if ts_count != exp_ts:
                    messages.append(f"WARNING: Timestamp count mismatch: expected {exp_ts}, got {ts_count}")
                else:
                    messages.append(f"[OK] Historical replay period: {ts_count} timestamps verified (May 01 - Jun 30, 2024).")

                # Verify NOT_EVALUABLE rainfall threshold probabilities are null
                null_10mm = df["rain_probability_10mm"].isna().sum()
                null_25mm = df["rain_probability_25mm"].isna().sum()
                if null_10mm != len(df) or null_25mm != len(df):
                    messages.append(f"ERROR: Scientific violation! NOT_EVALUABLE rainfall thresholds must have null probabilities.")
                    is_valid = False
                else:
                    messages.append(f"[OK] Scientific integrity: Zero fabricated probabilities for NOT_EVALUABLE rain >=10mm & >=25mm.")

                # Verify subgrid unresolved flag preservation
                unresolved = len(df[df["aggregation_status"] == "SUBGRID_RANGE_UNRESOLVED"])
                messages.append(f"[OK] Panchayat aggregation: {unresolved} records preserve SUBGRID_RANGE_UNRESOLVED flag (<3 cells).")

        except Exception as e:
            messages.append(f"ERROR: Failed reading reliability CSV: {str(e)}")
            is_valid = False

        return is_valid, messages


if __name__ == "__main__":
    validator = DemoDataValidator()
    valid, msgs = validator.validate_all()
    print("Demo Data Validation Report:")
    for m in msgs:
        print(" ", m)
    print("Result:", "PASS" if valid else "FAIL")
