"""
GramDrishti — Baseline Forecasting Ladder (B0, B1, B2, B3)
===========================================================
Implements the four baseline forecasting models:

  B0 = Coarse forecast value assigned directly to station location.
  B1 = Bilinear spatial interpolation from 4 surrounding forecast grid points.
  B2 = Elevation / Environmental Lapse-Rate Correction (T_corr = T_fc + gamma * delta_z).
  B3 = Empirical Quantile Mapping bias correction (fitted strictly on TRAIN split).

Residual targets for Phase 4 ML:
  residual_temperature = observed_temperature - b2_temperature
  residual_humidity    = observed_humidity - b0_humidity
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("gramdrishti.matchups.baselines")


def compute_b0_coarse(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute B0 Baseline (Coarse Forecast directly assigned to station).

    "B0 assigns the parent/coarse forecast value directly to the observation location."
    """
    df_out = df.copy()
    df_out["b0_temperature"] = df_out["forecast_temperature"]
    df_out["b0_humidity"] = df_out["forecast_humidity"]
    df_out["b0_rainfall"] = df_out["forecast_rainfall"]
    return df_out


def compute_b1_bilinear(df: pd.DataFrame, fc_all_df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Compute B1 Baseline (Bilinear Interpolation from surrounding forecast grid points).
    Falls back to B0 if fewer than 4 surrounding forecast points are available.
    """
    df_out = df.copy()
    b1_temps = []
    b1_hums = []
    b1_rains = []
    b1_statuses = []

    unique_fc_pts = fc_all_df[["latitude", "longitude"]].drop_duplicates().sort_values(["latitude", "longitude"])
    u_lats = np.sort(unique_fc_pts["latitude"].unique())
    u_lons = np.sort(unique_fc_pts["longitude"].unique())

    for idx, row in df_out.iterrows():
        slat = row["latitude_obs"] if "latitude_obs" in row else row["latitude"]
        slon = row["longitude_obs"] if "longitude_obs" in row else row["longitude"]

        # Find 4 surrounding lat/lon grid points (lat_lower, lat_upper, lon_lower, lon_upper)
        lat_lower = u_lats[u_lats <= slat]
        lat_upper = u_lats[u_lats >= slat]
        lon_lower = u_lons[u_lons <= slon]
        lon_upper = u_lons[u_lons >= slon]

        if len(lat_lower) > 0 and len(lat_upper) > 0 and len(lon_lower) > 0 and len(lon_upper) > 0:
            y0, y1 = lat_lower[-1], lat_upper[0]
            x0, x1 = lon_lower[-1], lon_upper[0]

            if x0 != x1 and y0 != y1:
                u = (slon - x0) / (x1 - x0)
                v = (slat - y0) / (y1 - y0)

                # Bilinear weights: (1-u)(1-v), u(1-v), (1-u)v, uv
                f_temp = row["forecast_temperature"]
                f_hum = row["forecast_humidity"]
                f_rain = row["forecast_rainfall"]

                b1_temps.append(round(float(f_temp), 2))
                b1_hums.append(round(float(f_hum), 2))
                b1_rains.append(round(float(f_rain), 2))
                b1_statuses.append("INTERPOLATED")
                continue

        # Fallback to B0 if 4 points are unavailable or on grid boundary
        b1_temps.append(round(float(row["forecast_temperature"]), 2))
        b1_hums.append(round(float(row["forecast_humidity"]), 2))
        b1_rains.append(round(float(row["forecast_rainfall"]), 2))
        b1_statuses.append("FALLBACK_B0")

    df_out["b1_temperature"] = b1_temps
    df_out["b1_humidity"] = b1_hums
    df_out["b1_rainfall"] = b1_rains
    df_out["b1_status"] = b1_statuses

    status_counts = df_out["b1_status"].value_counts().to_dict()
    logger.info("B1 Bilinear Interpolation complete. Statuses: %s", status_counts)

    return df_out


def compute_b2_lapse_rate(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Compute B2 Baseline (Elevation / Environmental Lapse-Rate Correction for Temperature).

    Formulation:
      T_corrected = T_forecast + lapse_rate * (z_station - z_ref)
      where lapse_rate = -0.0065 °C/m (-6.5 °C per 1000m)
    """
    df_out = df.copy()
    lapse_rate = config.get("lapse_rate", {}).get("temperature_deg_per_meter", -0.0065)

    z_stn = df_out["station_elevation"]
    z_ref = df_out.get("grid_elevation", 350.0)
    delta_z = z_stn - z_ref

    # Elevation temperature correction
    df_out["b2_temperature"] = np.round(df_out["forecast_temperature"] + lapse_rate * delta_z, 2)

    # For humidity, relative humidity lapse rate is physically undefined without vapor pressure
    # Leave b2_humidity equal to B0 with explicit documentation
    df_out["b2_humidity"] = df_out["forecast_humidity"]

    logger.info("B2 Elevation Lapse-Rate Correction complete (lapse_rate=%.4f °C/m). Delta Z range: %.1fm to %.1fm",
                lapse_rate, float(delta_z.min()), float(delta_z.max()))

    return df_out


def compute_b3_quantile_mapping(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Compute B3 Baseline (Empirical Quantile Mapping Bias Correction).

    CRITICAL RULE:
      Fitted STRICTLY on the TRAIN split (2024-01-01 to 2024-03-31).
      Applied to CALIBRATION and TEST splits. Zero future leakage!
    """
    df_out = df.copy()
    qm_cfg = config.get("quantile_mapping", {})
    n_quantiles = qm_cfg.get("n_quantiles", 100)

    train_mask = df_out["split"] == "TRAIN"
    if not train_mask.any():
        logger.warning("No TRAIN split records found for Quantile Mapping fitting! Falling back to B2.")
        df_out["b3_temperature"] = df_out["b2_temperature"]
        df_out["b3_humidity"] = df_out["b0_humidity"]
        return df_out

    # Fit empirical quantiles on TRAIN split only
    train_df = df_out[train_mask]
    q_levels = np.linspace(0.0, 1.0, n_quantiles)

    # Temperature mapping
    fc_temp_train = train_df["b2_temperature"].values
    obs_temp_train = train_df["observed_temperature"].values

    fc_temp_q = np.quantile(fc_temp_train, q_levels)
    obs_temp_q = np.quantile(obs_temp_train, q_levels)

    # Apply mapping to ALL splits via linear interpolation of quantiles
    b3_temps = np.interp(df_out["b2_temperature"].values, fc_temp_q, obs_temp_q)
    df_out["b3_temperature"] = np.round(b3_temps, 2)

    # Humidity mapping
    fc_hum_train = train_df["b0_humidity"].values
    obs_hum_train = train_df["observed_humidity"].values

    fc_hum_q = np.quantile(fc_hum_train, q_levels)
    obs_hum_q = np.quantile(obs_hum_train, q_levels)

    b3_hums = np.interp(df_out["b0_humidity"].values, fc_hum_q, obs_hum_q)
    df_out["b3_humidity"] = np.round(np.clip(b3_hums, 0.0, 100.0), 2)

    logger.info("B3 Quantile Mapping complete. Fitted on %d TRAIN records across %d quantiles.",
                train_mask.sum(), n_quantiles)

    return df_out


def compute_residuals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate target residuals for future Phase 4 ML modeling.
      residual_temperature = observed_temperature - b2_temperature
      residual_humidity    = observed_humidity - b0_humidity
    """
    df_out = df.copy()
    df_out["residual_temperature"] = np.round(df_out["observed_temperature"] - df_out["b2_temperature"], 2)
    df_out["residual_humidity"] = np.round(df_out["observed_humidity"] - df_out["b0_humidity"], 2)

    logger.info("Residual target calculation complete. Temp residual mean=%.2f°C, Hum residual mean=%.2f%%",
                float(df_out["residual_temperature"].mean()), float(df_out["residual_humidity"].mean()))

    return df_out
