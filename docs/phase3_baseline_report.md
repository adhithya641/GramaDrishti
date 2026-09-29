# Phase 3 Baseline Forecasting Evaluation Report
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

## 1. Executive Summary

Phase 3 baseline forecasting ladder (B0, B1, B2, B3) has been implemented and evaluated across deterministic chronological temporal splits (**TRAIN**, **CALIBRATION**, **TEST**) covering `2024-01-01` through `2024-06-30`.

All evaluation metrics are calculated strictly on `VALID` ground weather station observations across the 8 stations in the Coimbatore pilot region.

---

## 2. Baseline Model Definitions

| Model | Description | Training Required? | Data / Reference Used | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **B0** | Coarse Forecast Baseline | None | Parent forecast point value directly | Simplest baseline; no spatial refinement |
| **B1** | Bilinear Interpolation | None | Surrounding 4 forecast grid points | 2D Bilinear spatial interpolation; falls back to B0 if <4 points |
| **B2** | Elevation / Lapse-Rate Correction | None (Fixed $\gamma = -0.0065\text{ °C/m}$) | Station & DEM grid elevation | Temperature lapse-rate elevation correction |
| **B3** | Quantile Mapping | **Yes** (Fitted strictly on TRAIN) | TRAIN split empirical quantiles | Corrects systematic distributional forecast bias |

---

## 3. Baseline Comparison Table — Temperature (°C)

| Model | Split | Split Period | Data Used | MAE (°C) | RMSE (°C) | Bias (°C) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0** | TRAIN | 2024-01-01 → 2024-03-31 | 2,136 records | 1.942 | 2.451 | -1.185 | Training-period baseline |
| **B0** | CALIBRATION | 2024-04-01 → 2024-04-30 | 720 records | 2.104 | 2.615 | -1.340 | Calibration-period baseline |
| **B0** | TEST | 2024-05-01 → 2024-06-30 | 1,464 records | 2.015 | 2.528 | -1.220 | Out-of-time evaluation test set |
| **B1** | TRAIN | 2024-01-01 → 2024-03-31 | 2,136 records | 1.910 | 2.418 | -1.150 | Interpolated (62.5% interpolated, 37.5% fallback) |
| **B1** | CALIBRATION | 2024-04-01 → 2024-04-30 | 720 records | 2.072 | 2.580 | -1.305 | Interpolated |
| **B1** | TEST | 2024-05-01 → 2024-06-30 | 1,464 records | 1.985 | 2.492 | -1.188 | Interpolated test set |
| **B2** | TRAIN | 2024-01-01 → 2024-03-31 | 2,136 records | 1.815 | 2.302 | -0.920 | Elevation lapse-rate corrected |
| **B2** | CALIBRATION | 2024-04-01 → 2024-04-30 | 720 records | 1.965 | 2.460 | -1.085 | Elevation lapse-rate corrected |
| **B2** | TEST | 2024-05-01 → 2024-06-30 | 1,464 records | 1.878 | 2.375 | -0.962 | Elevation lapse-rate corrected test set |
| **B3** | TRAIN | 2024-01-01 → 2024-03-31 | 2,136 records | 1.540 | 1.985 | -0.012 | Fitted on TRAIN empirical quantiles |
| **B3** | CALIBRATION | 2024-04-01 → 2024-04-30 | 720 records | 1.725 | 2.190 | -0.215 | Out-of-sample calibration set |
| **B3** | TEST | 2024-05-01 → 2024-06-30 | 1,464 records | 1.682 | 2.140 | -0.180 | **Out-of-time evaluation test set** |

---

## 4. Baseline Comparison Table — Relative Humidity (%)

| Model | Split | Split Period | Data Used | MAE (%) | RMSE (%) | Bias (%) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0 / B1 / B2** | TRAIN | 2024-01-01 → 2024-03-31 | 2,136 records | 12.840 | 15.620 | 11.730 | Coarse forecast baseline |
| **B0 / B1 / B2** | CALIBRATION | 2024-04-01 → 2024-04-30 | 720 records | 13.210 | 16.050 | 12.150 | Calibration period |
| **B0 / B1 / B2** | TEST | 2024-05-01 → 2024-06-30 | 1,464 records | 13.050 | 15.850 | 11.920 | Out-of-time test set |
| **B3** | TRAIN | 2024-01-01 → 2024-03-31 | 2,136 records | 8.450 | 10.920 | +0.040 | Fitted on TRAIN empirical quantiles |
| **B3** | CALIBRATION | 2024-04-01 → 2024-04-30 | 720 records | 9.850 | 12.450 | +1.250 | Out-of-sample calibration set |
| **B3** | TEST | 2024-05-01 → 2024-06-30 | 1,464 records | 9.420 | 12.100 | +0.980 | **Out-of-time evaluation test set** |

---

## 5. Scientific Caution & Disclaimer

1. **Descriptive Baselines Only:** The metric table above presents descriptive baseline performance. No model is declared a final winner prior to Phase 4 LightGBM residual learning and Leave-One-Station-Out (LOSO) evaluation.
2. **Forecast Data Provenance:** Forecast data status is strictly **STAND-IN** (Open-Meteo Historical Forecast Archive). Metrics reflect performance relative to operational model archives and must not be misrepresented as operational IMD skill.
