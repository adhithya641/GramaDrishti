# Phase 4 LightGBM Residual Correction Evaluation Report
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

## 1. Executive Summary

Phase 4 evaluates the **LightGBM GBDT residual-correction model** for temperature (°C) and relative humidity (%) against the full baseline ladder (**B0**, **B1**, **B2**, **B3**) on the out-of-time evaluation **TEST** split (`2024-05-01` to `2024-06-30`, 1,464 records across 8 weather stations in Coimbatore District).

All metrics in this report are generated from the single canonical evaluation DataFrame (`data/processed/predictions/weather_predictions.csv`).

---

## 2. Test Set Baseline & ML Comparison Table

Bias is defined canonically as $\text{Bias} = \text{mean}(y_{\text{pred}} - y_{\text{true}})$.

### 2.1 Temperature (°C) — Test Period (`2024-05-01` → `2024-06-30`, 1,464 records)

| Model | Description | MAE (°C) | RMSE (°C) | Bias (°C) | Improvement vs B2 (%) | Improvement vs B3 (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0** | Coarse Forecast Baseline | 2.3165 | 2.9572 | +0.4376 | — | — |
| **B1** | Bilinear Interpolation | 2.3165 | 2.9572 | +0.4376 | 0.00% | -2.10% |
| **B2** | Elevation / Lapse-Rate Correction | 2.5332 | 3.1147 | +1.4013 | 0.00% | -7.04% |
| **B3** | Quantile Mapping (Fitted on TRAIN) | 2.3667 | 3.0669 | -0.3330 | +6.57% | 0.00% |
| **ML (Model A)**| Forecast + Temporal Features | **1.0823** | **1.3957** | **-0.3835** | **+57.27%** | **+54.27%** |
| **ML (Main)** | **Full Forecast + Time + GIS** | **1.2225** | **1.5077** | **-0.1752** | **+51.74%** | **+48.35%** |

### 2.2 Relative Humidity (%) — Test Period (`2024-05-01` → `2024-06-30`, 1,464 records)

| Model | Description | MAE (%) | RMSE (%) | Bias (%) | Improvement vs B2 (%) | Improvement vs B3 (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **B0/B1/B2**| Coarse / Bilinear / Elevation Baseline | 25.5342 | 27.8146 | -25.0350 | 0.00% | -14.96% |
| **B3** | Quantile Mapping (Fitted on TRAIN) | 22.2112 | 25.9185 | -20.4628 | +13.01% | 0.00% |
| **ML (Model A)**| Forecast + Temporal Features | **20.0937** | **21.8967** | **-19.3061** | **+21.31%** | **+9.53%** |
| **ML (Main)** | **Full Forecast + Time + GIS** | **19.4556** | **21.1212** | **-19.1396** | **+23.81%** | **+12.41%** |

---

## 3. Measured Skill Improvement Summary

1. **Temperature ML Performance:**
   - The Main ML model achieved a **TEST MAE of 1.2225 °C**, delivering a **+51.74% improvement over B2** (2.5332 °C) and a **+48.35% improvement over B3** (2.3667 °C).
2. **Humidity ML Performance:**
   - The Main ML model achieved a **TEST MAE of 19.4556 %**, delivering a **+23.81% improvement over B2** (25.5342 %) and a **+12.41% improvement over B3** (22.2112 %).

---

## 4. Feature Importance Analysis (SHAP & Gain)

Top features driving residual corrections across the 1,464 test instances:

### Top Temperature Features
1. `forecast_temperature` (Gain: 67,396.6, Mean Abs SHAP: 1.210 °C): Primary forecast anchor.
2. `elevation_mean` (Gain: 55,393.2, Mean Abs SHAP: 1.055 °C): Primary topographic predictor for spatial offset refinement.
3. `day_of_year_sin` & `day_of_year_cos` (Gain: 48,140.0, Mean Abs SHAP: 1.200 °C): Captures seasonal solar zenith angle shifts.
4. `b2_temperature` (Gain: 26,806.9, Mean Abs SHAP: 0.393 °C).
5. `elevation_std` & `elevation_range` (Gain: 13,060.6): Micro-relief variability.

---

## 5. Ablation Study: Terrain/GIS Feature Value

| Target | Model Setting | Features | MAE | RMSE | Bias | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Temperature** | Model A (Forecast + Time Only) | 8 | 1.0823 °C | 1.3957 °C | -0.3835 °C | Temporal baseline |
| **Temperature** | Model B (Full Forecast + Time + GIS) | 25 | 1.2225 °C | 1.5077 °C | -0.1752 °C | Full topographic model |
| **Humidity** | Model A (Forecast + Time Only) | 8 | 20.0937 % | 21.8967 % | -19.3061 % | Temporal baseline |
| **Humidity** | Model B (Full Forecast + Time + GIS) | 25 | **19.4556 %** | **21.1212 %** | **-19.1396 %** | Topographic model improves humidity by **+3.18%** over Model A |

> [!NOTE]
> **Scientific Finding:**
> For this Coimbatore pilot and evaluation period, adding GIS/terrain features improved humidity performance but did not improve temperature performance in the reported ablation. Therefore the experiment does not establish that terrain features universally improve temperature forecasts.

---

## 6. Station-Wise Performance Breakdown (TEST Period: 183 Records Per Station)

| Station ID | Elevation | Group | Records | B2 Temp MAE (°C) | B3 Temp MAE (°C) | ML Temp MAE (°C) | ML vs B3 Imp (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `STN_CBE_01` | 409 m | LOW | 183 | 2.5932 | 2.2042 | **0.9122** | **+58.62%** |
| `STN_CBE_02` | 426 m | LOW | 183 | 3.4711 | 2.2912 | **0.8155** | **+64.41%** |
| `STN_CBE_03` | 293 m | LOW | 183 | 2.1135 | 2.4050 | **1.1723** | **+51.26%** |
| `STN_CBE_04` | 322 m | LOW | 183 | 2.5260 | 1.7652 | **1.4329** | **+18.83%** |
| `STN_CBE_05` | 338 m | LOW | 183 | 2.0869 | 2.8843 | **1.0828** | **+62.46%** |
| `STN_CBE_06` | 1050 m | HIGH | 183 | 2.7065 | 2.5119 | **2.0799** | **+17.20%** |
| `STN_CBE_07` | 308 m | LOW | 183 | 2.5670 | 2.3198 | **1.1582** | **+50.07%** |
| `STN_CBE_08` | 380 m | LOW | 183 | 2.2013 | 2.5517 | **1.1259** | **+55.88%** |

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
