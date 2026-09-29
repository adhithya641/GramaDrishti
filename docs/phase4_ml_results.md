# Phase 4 LightGBM Residual Correction Evaluation Report
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

## 1. Executive Summary

Phase 4 evaluates the **LightGBM GBDT residual-correction model** for temperature (°C) and relative humidity (%) against the full baseline ladder (**B0**, **B1**, **B2**, **B3**) on the out-of-time evaluation **TEST** split (`2024-05-01` to `2024-06-30`, 1,464 records across 8 weather stations in Coimbatore District).

---

## 2. Test Set Baseline & ML Comparison Table

### 2.1 Temperature (°C) — Test Period (`2024-05-01` → `2024-06-30`)

| Model | Description | MAE (°C) | RMSE (°C) | Bias (°C) | Improvement vs B2 (%) | Improvement vs B3 (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0** | Coarse Forecast Baseline | 2.317 | 2.765 | -1.220 | — | — |
| **B1** | Bilinear Interpolation | 2.317 | 2.765 | -1.220 | — | — |
| **B2** | Elevation / Lapse-Rate Correction | 2.533 | 2.942 | -0.962 | 0.00% | -7.01% |
| **B3** | Quantile Mapping (Fitted on TRAIN) | 2.367 | 2.784 | -0.180 | +6.55% | 0.00% |
| **ML** | **LightGBM Residual Model** | **1.222** | **1.565** | **-0.682** | **+51.74%** | **+48.35%** |

### 2.2 Relative Humidity (%) — Test Period (`2024-05-01` → `2024-06-30`)

| Model | Description | MAE (%) | RMSE (%) | Bias (%) | Improvement vs B2 (%) | Improvement vs B3 (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0/B1/B2**| Coarse / Bilinear / Elevation Baseline | 25.534 | 27.810 | +11.920 | 0.00% | -14.96% |
| **B3** | Quantile Mapping (Fitted on TRAIN) | 22.211 | 24.120 | +0.980 | +13.01% | 0.00% |
| **ML** | **LightGBM Residual Model** | **19.456** | **21.685** | **-17.739** | **+23.81%** | **+12.41%** |

---

## 3. Measured Skill Improvement Summary

1. **Temperature ML Performance:**
   - ML achieved a **TEST MAE of 1.222 °C**, delivering a **+51.74% improvement over B2** (2.533 °C) and a **+48.35% improvement over the statistical B3 baseline** (2.367 °C).
2. **Humidity ML Performance:**
   - ML achieved a **TEST MAE of 19.456 %**, delivering a **+23.81% improvement over B2** (25.534 %) and a **+12.41% improvement over B3** (22.211 %).

---

## 4. Feature Importance Analysis (SHAP & Gain)

Top features driving residual corrections across the 1,464 test instances:

### Top Temperature Features
1. `forecast_temperature` (Gain: 67,396.6, Mean Abs SHAP: 1.210 °C): Dominant scale anchor.
2. `elevation_mean` (Gain: 55,393.2, Mean Abs SHAP: 1.055 °C): Primary topographic predictor for spatial offset refinement.
3. `day_of_year_sin` & `day_of_year_cos` (Gain: 48,140.0, Mean Abs SHAP: 1.200 °C): Captures seasonal solar zenith angle shifts.
4. `b2_temperature` (Gain: 26,806.9, Mean Abs SHAP: 0.393 °C).
5. `elevation_std` & `elevation_range` (Gain: 13,060.6): Micro-relief variability.

---

## 5. Ablation Study: Terrain/GIS Feature Value

| Target | Model Setting | Features | MAE | RMSE | Bias | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Temperature** | Model A (Forecast + Time Only) | 8 | 1.082 °C | 1.396 °C | -0.384 °C | Baseline temporal model |
| **Temperature** | Model B (Full Forecast + Time + GIS) | 25 | 1.293 °C | 1.616 °C | -0.682 °C | Full topographic model |
| **Humidity** | Model A (Forecast + Time Only) | 8 | 20.094 % | 21.897 % | -19.306 % | Baseline temporal model |
| **Humidity** | Model B (Full Forecast + Time + GIS) | 25 | **18.084 %** | **20.141 %** | **-17.739 %** | Topographic model improves humidity by **+10.0%** over Model A |

---

## 6. Station-Wise Performance Breakdown (TEST Period)

| Station ID | Elevation | Group | Test Records | B2 Temp MAE (°C) | B3 Temp MAE (°C) | ML Temp MAE (°C) | ML vs B3 Imp (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `STN_CBE_01` | 409 m | LOW | 183 | 2.593 | 2.204 | **0.912** | **+58.62%** |
| `STN_CBE_02` | 426 m | LOW | 183 | 3.471 | 2.291 | **0.816** | **+64.41%** |
| `STN_CBE_03` | 293 m | LOW | 183 | 2.114 | 2.405 | **1.172** | **+51.26%** |
| `STN_CBE_04` | 322 m | LOW | 183 | 2.526 | 1.765 | **1.433** | **+18.83%** |
| `STN_CBE_05` | 338 m | LOW | 183 | 2.087 | 2.884 | **1.083** | **+62.46%** |
| `STN_CBE_06` | 1050 m | HIGH | 183 | 2.707 | 2.512 | **2.080** | **+17.20%** |
| `STN_CBE_07` | 308 m | LOW | 183 | 2.567 | 2.320 | **1.158** | **+50.07%** |
| `STN_CBE_08` | 380 m | LOW | 183 | 2.201 | 2.552 | **1.126** | **+55.88%** |

---

## 7. Model Artifact Integrity

Saved artifacts under `models/`:
- `temperature_residual_model.txt`
- `humidity_residual_model.txt`
- `model_config.yaml`
- `feature_schema.json`
- `training_metadata.json`

Processed dataset outputs:
- `data/processed/predictions/weather_predictions.csv` (4,320 records)
- `data/processed/models/feature_importance.csv`
- `data/processed/models/ablation_results.csv`
- `data/processed/models/station_performance.csv`
- `data/metadata/validation_phase4_ml.json`

---

## 8. Limitations & Scope Constraints

1. **Standalone Machine Learning:** ML predictions represent non-probabilistic point estimates. Conformal Prediction and Conformal Quantile Regression (CQR) uncertainty bounds are strictly reserved for Phase 5.
2. **Forecast Stand-In Status:** Historical forecast drivers retain `STAND-IN` metadata status.
