"""
GramDrishti — Phase 8 Data Loader (Read-Only)
==============================================
Safe data loader for existing project artifacts with robust missing-data handling.
Treats all underlying artifacts as strictly READ-ONLY.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np

from app.schemas import (
    PanchayatInfo,
    WeatherForecastData,
    RainfallForecastData,
    SystemStatusReport,
    FreshnessStatus,
    AggregationStatus,
    validate_temperature,
    validate_humidity,
    validate_probability,
    validate_uncertainty_ordering,
    validate_panchayat_id,
    parse_datetime_safe,
)

logger = logging.getLogger(__name__)

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent


def get_path(rel_path: str) -> Path:
    return BASE_DIR / rel_path


class DataLoader:
    """Safe, cached data loader for GramDrishti artifacts."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or BASE_DIR

    def path(self, rel_path: str) -> Path:
        return self.base_dir / rel_path

    def exists(self, rel_path: str) -> bool:
        return self.path(rel_path).is_file()

    # -------------------------------------------------------------
    # Metadata & Panchayat Geometries
    # -------------------------------------------------------------
    def load_panchayats(self) -> List[PanchayatInfo]:
        """Loads and compiles 180 Panchayats metadata dynamically from available artifacts."""
        panchayats_map: Dict[str, PanchayatInfo] = {}

        # 1. Try loading from GeoJSON
        geojson_path = self.path("data/processed/boundaries/coimbatore_panchayats_processed.geojson")
        if geojson_path.is_file():
            try:
                with open(geojson_path, "r", encoding="utf-8") as f:
                    gj = json.load(f)
                for feat in gj.get("features", []):
                    props = feat.get("properties", {})
                    p_id = props.get("panchayat_code") or props.get("panchayat_id")
                    if not p_id:
                        continue
                    # Compute simple polygon centroid if coords available
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    lat, lon = 11.0, 77.0  # default
                    if coords:
                        try:
                            # If Polygon, coords[0] is ring of [lon, lat]
                            poly = coords[0] if feat["geometry"]["type"] == "Polygon" else coords[0][0]
                            lons = [pt[0] for pt in poly]
                            lats = [pt[1] for pt in poly]
                            lon = float(np.mean(lons))
                            lat = float(np.mean(lats))
                        except Exception:
                            pass

                    panchayats_map[p_id] = PanchayatInfo(
                        panchayat_id=p_id,
                        panchayat_name=props.get("panchayat_name", p_id),
                        block_name=props.get("block_name", "Unknown"),
                        district_name=props.get("district_name", "Coimbatore"),
                        latitude=lat,
                        longitude=lon,
                        elevation_mean=0.0,
                        area_sq_km=props.get("area_sq_km", None),
                    )
            except Exception as e:
                logger.warning(f"Could not parse geojson boundaries: {e}")

        # 2. Enrich from geospatial_features_master.csv if exists
        master_path = self.path("data/processed/geospatial/geospatial_features_master.csv")
        if master_path.is_file():
            try:
                df = pd.read_csv(master_path)
                gp_grouped = df.groupby("panchayat_id")
                for p_id, group in gp_grouped:
                    p_name = group["panchayat_name"].iloc[0] if "panchayat_name" in group else p_id
                    b_name = group["block_name"].iloc[0] if "block_name" in group else "Coimbatore"
                    d_name = group["district_name"].iloc[0] if "district_name" in group else "Coimbatore"
                    lat = float(group["latitude"].mean()) if "latitude" in group else 11.0
                    lon = float(group["longitude"].mean()) if "longitude" in group else 77.0
                    elev = float(group["elevation_mean"].mean()) if "elevation_mean" in group else 0.0
                    cells = len(group)
                    mode = group["assignment_mode"].iloc[0] if "assignment_mode" in group else "CONTAINMENT"

                    if p_id in panchayats_map:
                        panchayats_map[p_id].panchayat_name = p_name
                        panchayats_map[p_id].block_name = b_name
                        panchayats_map[p_id].district_name = d_name
                        panchayats_map[p_id].latitude = lat
                        panchayats_map[p_id].longitude = lon
                        panchayats_map[p_id].elevation_mean = round(elev, 1)
                        panchayats_map[p_id].grid_cell_count = cells
                        panchayats_map[p_id].assignment_mode = mode
                    else:
                        panchayats_map[p_id] = PanchayatInfo(
                            panchayat_id=p_id,
                            panchayat_name=p_name,
                            block_name=b_name,
                            district_name=d_name,
                            latitude=lat,
                            longitude=lon,
                            elevation_mean=round(elev, 1),
                            grid_cell_count=cells,
                            assignment_mode=mode,
                        )
            except Exception as e:
                logger.warning(f"Could not load geospatial features master: {e}")

        # 3. If neither provided, check panchayat_rainfall_predictions.csv
        if not panchayats_map:
            pr_path = self.path("data/processed/predictions/panchayat_rainfall_predictions.csv")
            if pr_path.is_file():
                df_pr = pd.read_csv(pr_path)
                for p_id in df_pr["panchayat_id"].unique():
                    panchayats_map[p_id] = PanchayatInfo(
                        panchayat_id=p_id,
                        panchayat_name=f"Panchayat {p_id}",
                        block_name="Coimbatore",
                        district_name="Coimbatore",
                        latitude=11.0,
                        longitude=77.0,
                        elevation_mean=400.0,
                    )

        # 4. Attach nearest station info
        stations = self.load_stations_metadata()
        for p_id, p_info in panchayats_map.items():
            if stations:
                best_stn = None
                min_dist = float("inf")
                for s in stations:
                    # Approx Euclidean distance in km: 1 deg ~ 111 km
                    d = np.sqrt(((p_info.latitude - s["latitude"]) * 111) ** 2 + ((p_info.longitude - s["longitude"]) * 111 * np.cos(np.radians(p_info.latitude))) ** 2)
                    if d < min_dist:
                        min_dist = d
                        best_stn = s["station_id"]
                p_info.nearest_station_id = best_stn
                p_info.nearest_station_distance_km = round(min_dist, 2)

        return sorted(list(panchayats_map.values()), key=lambda x: x.panchayat_name)

    def load_geojson(self) -> Optional[Dict[str, Any]]:
        """Loads GeoJSON dictionary for map display."""
        path = self.path("data/processed/boundaries/coimbatore_panchayats_processed.geojson")
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading GeoJSON: {e}")
            return None

    def load_stations_metadata(self) -> List[Dict[str, Any]]:
        """Loads metadata for the 8 IMD / Observation stations."""
        sr_path = self.path("data/processed/predictions/station_rainfall_predictions.csv")
        if sr_path.is_file():
            try:
                df = pd.read_csv(sr_path)
                sub = df[["station_id", "panchayat_id", "panchayat_name", "block_name", "latitude", "longitude", "station_elevation"]].drop_duplicates("station_id")
                return sub.to_dict(orient="records")
            except Exception:
                pass
        # Fallback to weather_matchups if needed
        wm_path = self.path("data/processed/matchups/weather_matchups.csv")
        if wm_path.is_file():
            try:
                df = pd.read_csv(wm_path)
                sub = df[["station_id", "panchayat_id", "latitude_obs", "longitude_obs", "station_elevation"]].drop_duplicates("station_id")
                stations = []
                for _, r in sub.iterrows():
                    stations.append({
                        "station_id": r["station_id"],
                        "panchayat_id": r["panchayat_id"],
                        "panchayat_name": f"Station Host {r['panchayat_id']}",
                        "block_name": "Coimbatore",
                        "latitude": r["latitude_obs"],
                        "longitude": r["longitude_obs"],
                        "station_elevation": r["station_elevation"],
                    })
                return stations
            except Exception:
                pass
        return []

    # -------------------------------------------------------------
    # Weather Forecast & Uncertainty Data (Phase 4 & 5)
    # -------------------------------------------------------------
    def load_weather_forecasts_df(self) -> pd.DataFrame:
        """Loads merged weather predictions and uncertainty predictions DataFrame."""
        w_path = self.path("data/processed/predictions/weather_predictions.csv")
        u_path = self.path("data/processed/predictions/uncertainty_predictions.csv")

        if not w_path.is_file():
            return pd.DataFrame()

        df_w = pd.read_csv(w_path)

        if u_path.is_file():
            df_u = pd.read_csv(u_path)
            # Merge on ['station_id', 'observation_time', 'lead_time_hours']
            merge_cols = ["station_id", "observation_time", "lead_time_hours"]
            u_cols = [c for c in df_u.columns if c not in df_w.columns or c in merge_cols]
            df_merged = pd.merge(df_w, df_u[u_cols], on=merge_cols, how="left")
            return df_merged
        return df_w

    def get_station_weather_forecast(
        self,
        station_id: str,
        timestamp: Optional[str] = None,
        lead_time: Optional[int] = None
    ) -> Optional[WeatherForecastData]:
        """Fetches validated weather forecast for a station."""
        df = self.load_weather_forecasts_df()
        if df.empty:
            return None

        sub = df[df["station_id"] == station_id]
        if sub.empty:
            return None

        if timestamp:
            sub = sub[sub["observation_time"] == timestamp]
        if lead_time:
            sub = sub[sub["lead_time_hours"] == lead_time]

        if sub.empty:
            return None

        row = sub.iloc[-1]

        # Extract values
        ml_temp = row.get("ml_temperature")
        ml_hum = row.get("ml_humidity")
        q10_t = row.get("q10_temperature")
        q50_t = row.get("q50_temperature")
        q90_t = row.get("q90_temperature")
        q10_h = row.get("q10_humidity")
        q50_h = row.get("q50_humidity")
        q90_h = row.get("q90_humidity")

        # Validate
        v_temp = validate_temperature(ml_temp)
        v_hum = validate_humidity(ml_hum)
        is_valid = v_temp.is_valid and v_hum.is_valid
        err = None
        if not is_valid:
            err = f"Validation failed: Temp: {v_temp.error_message or 'OK'}, Hum: {v_hum.error_message or 'OK'}"

        # Uncertainty Ordering Validation
        if q10_t is not None and q50_t is not None and q90_t is not None:
            v_ord_t = validate_uncertainty_ordering(q10_t, q50_t, q90_t)
            if not v_ord_t.is_valid:
                is_valid = False
                err = (err or "") + f" | {v_ord_t.error_message}"

        if q10_h is not None and q50_h is not None and q90_h is not None:
            v_ord_h = validate_uncertainty_ordering(q10_h, q50_h, q90_h)
            if not v_ord_h.is_valid:
                is_valid = False
                err = (err or "") + f" | {v_ord_h.error_message}"

        return WeatherForecastData(
            station_id=station_id,
            panchayat_id=row.get("panchayat_id"),
            observation_time=str(row.get("observation_time", "")),
            valid_time=str(row.get("valid_time", "")),
            lead_time_hours=int(row.get("lead_time_hours", 24)),
            ml_temperature=float(ml_temp) if ml_temp is not None and not np.isnan(ml_temp) else None,
            ml_humidity=float(ml_hum) if ml_hum is not None and not np.isnan(ml_hum) else None,
            observed_temperature=float(row["observed_temperature"]) if "observed_temperature" in row and pd.notnull(row["observed_temperature"]) else None,
            observed_humidity=float(row["observed_humidity"]) if "observed_humidity" in row and pd.notnull(row["observed_humidity"]) else None,
            b0_temperature=float(row["b0_temperature"]) if "b0_temperature" in row and pd.notnull(row["b0_temperature"]) else None,
            b1_temperature=float(row["b1_temperature"]) if "b1_temperature" in row and pd.notnull(row["b1_temperature"]) else None,
            b2_temperature=float(row["b2_temperature"]) if "b2_temperature" in row and pd.notnull(row["b2_temperature"]) else None,
            b3_temperature=float(row["b3_temperature"]) if "b3_temperature" in row and pd.notnull(row["b3_temperature"]) else None,
            b0_humidity=float(row["b0_humidity"]) if "b0_humidity" in row and pd.notnull(row["b0_humidity"]) else None,
            b1_humidity=float(row["b1_humidity"]) if "b1_humidity" in row and pd.notnull(row["b1_humidity"]) else None,
            b2_humidity=float(row["b2_humidity"]) if "b2_humidity" in row and pd.notnull(row["b2_humidity"]) else None,
            b3_humidity=float(row["b3_humidity"]) if "b3_humidity" in row and pd.notnull(row["b3_humidity"]) else None,
            q10_temperature=float(q10_t) if q10_t is not None and pd.notnull(q10_t) else None,
            q50_temperature=float(q50_t) if q50_t is not None and pd.notnull(q50_t) else None,
            q90_temperature=float(q90_t) if q90_t is not None and pd.notnull(q90_t) else None,
            q10_humidity=float(q10_h) if q10_h is not None and pd.notnull(q10_h) else None,
            q50_humidity=float(q50_h) if q50_h is not None and pd.notnull(q50_h) else None,
            q90_humidity=float(q90_h) if q90_h is not None and pd.notnull(q90_h) else None,
            temp_interval_width=float(row["temperature_interval_width"]) if "temperature_interval_width" in row and pd.notnull(row["temperature_interval_width"]) else None,
            hum_interval_width=float(row["humidity_interval_width"]) if "humidity_interval_width" in row and pd.notnull(row["humidity_interval_width"]) else None,
            temperature_reliability=str(row.get("temperature_reliability", "MEDIUM")),
            humidity_reliability=str(row.get("humidity_reliability", "LOW")),
            is_valid=is_valid,
            validation_error=err,
        )

    # -------------------------------------------------------------
    # Rainfall Predictions Data (Phase 6)
    # -------------------------------------------------------------
    def load_panchayat_rainfall_df(self) -> pd.DataFrame:
        """Loads Panchayat rainfall predictions CSV."""
        path = self.path("data/processed/predictions/panchayat_rainfall_predictions.csv")
        if not path.is_file():
            return pd.DataFrame()
        return pd.read_csv(path)

    def get_panchayat_rainfall_forecast(
        self,
        panchayat_id: str,
        timestamp: Optional[str] = None,
        lead_time: Optional[int] = None
    ) -> Optional[RainfallForecastData]:
        """Fetches validated Panchayat rainfall forecast."""
        df = self.load_panchayat_rainfall_df()
        if df.empty:
            return None

        sub = df[df["panchayat_id"] == panchayat_id]
        if sub.empty:
            return None

        if timestamp:
            sub = sub[sub["timestamp"] == timestamp]
        if lead_time:
            sub = sub[sub["lead_time"] == lead_time]

        if sub.empty:
            return None

        row = sub.iloc[-1]

        # In Phase 6, rain_probability_1mm is valid and calibrated.
        # rain_probability_10mm and 25mm are scientifically data-limited / not evaluable.
        # We preserve them as None (NOT_EVALUABLE) for scientific integrity.
        prob_1mm = row.get("rain_probability_1mm")
        prob_1mm_p10 = row.get("rain_probability_1mm_p10")
        prob_1mm_p90 = row.get("rain_probability_1mm_p90")
        spread_1mm = row.get("spatial_spread_1mm")
        status = str(row.get("aggregation_status", "OK"))
        cells = int(row.get("grid_cell_count", 1))

        # Validate probability in [0, 1]
        v_prob = validate_probability(prob_1mm)
        is_valid = v_prob.is_valid
        err = v_prob.error_message

        return RainfallForecastData(
            panchayat_id=panchayat_id,
            timestamp=str(row.get("timestamp", "")),
            lead_time=int(row.get("lead_time", 24)),
            rain_probability_1mm=float(prob_1mm) if prob_1mm is not None and pd.notnull(prob_1mm) else None,
            rain_probability_10mm=None,  # Strictly NOT_EVALUABLE / Data-limited
            rain_probability_25mm=None,  # Strictly NOT_EVALUABLE / Unobserved
            rain_probability_1mm_p10=float(prob_1mm_p10) if prob_1mm_p10 is not None and pd.notnull(prob_1mm_p10) else None,
            rain_probability_1mm_p90=float(prob_1mm_p90) if prob_1mm_p90 is not None and pd.notnull(prob_1mm_p90) else None,
            spatial_spread_1mm=float(spread_1mm) if spread_1mm is not None and pd.notnull(spread_1mm) else None,
            grid_cell_count=cells,
            aggregation_status=status,
            is_evaluable_10mm=False,
            is_evaluable_25mm=False,
            is_valid=is_valid,
            validation_error=err,
        )

    # -------------------------------------------------------------
    # Phase 7 Reliability & Advisory Check (Graceful Handling)
    # -------------------------------------------------------------
    def load_phase7_reliability(self) -> Optional[pd.DataFrame]:
        """Loads Phase 7 reliability data if present. Returns None if absent."""
        path = self.path("data/processed/predictions/panchayat_reliability.csv")
        if not path.is_file():
            return None
        try:
            return pd.read_csv(path)
        except Exception:
            return None

    def load_phase7_advisories(self) -> Optional[Any]:
        """Loads Phase 7 crop advisory data if present. Returns None if absent."""
        path = self.path("data/processed/predictions/crop_advisories.json")
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    # -------------------------------------------------------------
    # System Status & Freshness
    # -------------------------------------------------------------
    def get_system_status(self) -> SystemStatusReport:
        """Determines the live system status across all phases."""
        has_forecast = self.exists("data/processed/predictions/weather_predictions.csv")
        has_rainfall = self.exists("data/processed/predictions/panchayat_rainfall_predictions.csv")
        has_uncertainty = self.exists("data/processed/predictions/uncertainty_predictions.csv")
        has_reliability = self.exists("data/processed/predictions/panchayat_reliability.csv")
        has_advisory = self.exists("data/processed/predictions/crop_advisories.json")

        latest_ts = None
        freshness = FreshnessStatus.FRESH

        if has_rainfall:
            df_pr = self.load_panchayat_rainfall_df()
            if not df_pr.empty and "timestamp" in df_pr:
                latest_ts = str(df_pr["timestamp"].max())

        return SystemStatusReport(
            forecast_data_available=has_forecast,
            rainfall_model_available=has_rainfall,
            uncertainty_available=has_uncertainty,
            reliability_available=has_reliability,
            advisory_engine_available=has_advisory,
            pilot_region="Coimbatore District, Tamil Nadu",
            panchayat_count=180,
            station_count=8,
            latest_timestamp=latest_ts,
            freshness_status=freshness,
        )

    # -------------------------------------------------------------
    # Validation & Performance Metrics
    # -------------------------------------------------------------
    def load_model_performance(self) -> Dict[str, Any]:
        """Loads model evaluation metrics and comparison tables."""
        res: Dict[str, Any] = {}
        stn_perf_path = self.path("data/processed/models/station_performance.csv")
        if stn_perf_path.is_file():
            res["station_performance"] = pd.read_csv(stn_perf_path)

        feat_imp_path = self.path("data/processed/models/feature_importance.csv")
        if feat_imp_path.is_file():
            res["feature_importance"] = pd.read_csv(feat_imp_path)

        rain_cmp_path = self.path("data/processed/models/rainfall/model_metrics_comparison.csv")
        if rain_cmp_path.is_file():
            res["rainfall_metrics"] = pd.read_csv(rain_cmp_path)

        uq_val_path = self.path("data/metadata/validation_phase5_uncertainty.json")
        if uq_val_path.is_file():
            try:
                with open(uq_val_path, "r") as f:
                    res["uncertainty_validation"] = json.load(f)
            except Exception:
                pass

        rain_val_path = self.path("data/metadata/validation_phase6_rainfall.json")
        if rain_val_path.is_file():
            try:
                with open(rain_val_path, "r") as f:
                    res["rainfall_validation"] = json.load(f)
            except Exception:
                pass

        return res
