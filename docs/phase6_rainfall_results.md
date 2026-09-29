# GramDrishti — Phase 6: Rainfall Probability & Panchayat Aggregation Report

## 1. Objective

The objective of Phase 6 is to build, validate, and evaluate the rainfall-probability estimation pipeline of GramDrishti and aggregate spatial rainfall probabilities across the 180 Gram Panchayats in Coimbatore District.

Specifically, the model estimates:
1. $P(\text{Rain} \ge 1.0\text{ mm})$
2. $P(\text{Rain} \ge 10.0\text{ mm})$
3. $P(\text{Rain} \ge 25.0\text{ mm})$

The resulting grid-level probabilities are aggregated to panchayat-level outputs with spatial variability metrics and subgrid resolution status indicators.

---

## 2. Dataset & Quality Audit

The dataset consists of the locked, validated matchup dataset (`data/processed/matchups/weather_matchups.csv`) joined with the 1-km geospatial master feature table (`data/processed/geospatial/geospatial_features_master.csv`).

### Data Quality Audit Findings

| Data Quality Check | Audit Result | Status |
|-------------------|--------------|--------|
| **Missing Observed Rainfall** | 0 records | CLEAN |
| **Negative Rainfall Values** | 0 records | CLEAN |
| **Duplicate Timestamps** | 0 records | CLEAN |
| **Impossible Rainfall (> 500 mm)** | 0 records | CLEAN |
| **Unique Weather Stations** | 8 stations | VERIFIED |
| **Overall Data Audit** | **CLEAN** | **PASS** |

---

## 3. Event Definitions & Sample Statistics

Binary targets were constructed for each threshold:
- `rain_1mm`  = `observed_rainfall >= 1.0 mm`
- `rain_10mm` = `observed_rainfall >= 10.0 mm`
- `rain_25mm` = `observed_rainfall >= 25.0 mm`

### Split Event Summary

| Threshold | Split | Total Records | Event Count | Non-Event Count | Event Rate (%) |
|-----------|-------|---------------|-------------|-----------------|----------------|
| **1.0 mm** | TRAIN | 2,136 | 15 | 2,121 | **0.70%** |
| **1.0 mm** | CALIBRATION | 720 | 9 | 711 | **1.25%** |
| **1.0 mm** | TEST | 1,464 | 165 | 1,299 | **11.27%** |
| **10.0 mm** | TRAIN | 2,136 | 0 | 2,136 | **0.00%** |
| **10.0 mm** | CALIBRATION | 720 | 0 | 720 | **0.00%** |
| **10.0 mm** | TEST | 1,464 | 6 | 1,458 | **0.41%** |
| **25.0 mm** | TRAIN | 2,136 | 0 | 2,136 | **0.00%** |
| **25.0 mm** | CALIBRATION | 720 | 0 | 720 | **0.00%** |
| **25.0 mm** | TEST | 1,464 | 0 | 1,464 | **0.00%** |

*Note: Heavy rainfall events ($\ge 10\text{ mm}$ and $\ge 25\text{ mm}$) are extremely sparse or absent in the dry Jan–April period (TRAIN & CALIBRATION), appearing only in May–June (TEST) with the onset of the Southwest Monsoon.*

---

## 4. Chronological Splitting Strategy

The pipeline adheres strictly to the canonical chronological split used in Phases 3–5:

- **TRAIN**: 2024-01-01 to 2024-03-31 (2,136 records)
- **CALIBRATION**: 2024-04-01 to 2024-04-30 (720 records)
- **TEST**: 2024-05-01 to 2024-06-30 (1,464 records)

No random row splitting was performed. Held-out TEST data was never used for feature engineering, model fitting, or probability calibration.

---

## 5. R0 Baseline — Climatology

The R0 climatology model assigns a constant probability equal to the event rate observed in the **TRAIN set only**:
- $P_{R0}(\text{rain\_1mm}) = 15 / 2136 = 0.007022$
- $P_{R0}(\text{rain\_10mm}) = 0 / 2136 = 0.000000$
- $P_{R0}(\text{rain\_25mm}) = 0 / 2136 = 0.000000$

---

## 6. R1 Baseline — Logistic Regression

The R1 baseline fits a regularized `LogisticRegression` model on TRAIN set features available at forecast time (forecast weather, lead time, terrain features, land-cover fractions, cyclical time variables).
- Numeric features were imputed and standardized (`StandardScaler`).
- Strictly forbidden leakage features (station ID, observed weather, future variables) were excluded.
- Single-class targets (`rain_10mm` and `rain_25mm` in TRAIN) predict 0.0 probability.

---

## 7. R2 Model — LightGBM Binary Classifier

The R2 model fits one LightGBM binary classifier per threshold on TRAIN set features:
- Objective: `binary_logloss`
- Features: 27 non-leaking forecast, terrain, land-cover, hydrological, and temporal features.
- Categorical feature: `dominant_landcover_class`.
- Single-class targets predict 0.0 probability.

---

## 8. Isotonic Probability Calibration

To ensure well-calibrated probabilities, R2 predictions are calibrated using `IsotonicRegression(out_of_bounds='clip', y_min=0.0, y_max=1.0)`:
1. R2 is trained on TRAIN (Jan–Mar).
2. R2 predicts raw probabilities $P_{\text{calib}}$ on CALIBRATION (April).
3. `IsotonicRegression` is fitted on CALIBRATION ($P_{\text{calib}} \to Y_{\text{calib}}$).
4. The frozen calibrator transforms held-out TEST raw probabilities to calibrated probabilities.

---

## 9. Evaluation Metrics (TEST Set Performance)

For each threshold and model, performance on the held-out TEST set (n=1,464) is reported:

| Threshold | Model | Brier Score | POD | FAR | CSI | Predicted Prob Mean | Observed Event Rate |
|-----------|-------|-------------|-----|-----|-----|----------------------|---------------------|
| **1.0 mm** | **R0 Climatology** | **0.111171** | 0.0000 | 0.0000 | 0.0000 | 0.007022 | 0.112705 |
| **1.0 mm** | **R1 Logistic Regression** | **0.377202** | 0.4606 | 0.8952 | 0.0934 | 0.504927 | 0.112705 |
| **1.0 mm** | **R2 LightGBM Raw** | **0.112501** | 0.0000 | 0.0000 | 0.0000 | 0.001933 | 0.112705 |
| **1.0 mm** | **R2 LightGBM Calibrated** | **0.111466** | 0.0000 | 0.0000 | 0.0000 | 0.009478 | 0.112705 |
| **10.0 mm** | **R0 Climatology** | **0.004098** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.004098 |
| **10.0 mm** | **R1 Logistic Regression** | **0.004098** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.004098 |
| **10.0 mm** | **R2 LightGBM Raw** | **0.004098** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.004098 |
| **10.0 mm** | **R2 LightGBM Calibrated** | **0.004098** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.004098 |
| **25.0 mm** | **R0 Climatology** | **0.000000** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.000000 |
| **25.0 mm** | **R1 Logistic Regression** | **0.000000** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.000000 |
| **25.0 mm** | **R2 LightGBM Raw** | **0.000000** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.000000 |
| **25.0 mm** | **R2 LightGBM Calibrated** | **0.000000** | 0.0000 | 0.0000 | 0.0000 | 0.000000 | 0.000000 |

*Note: Lower Brier Score is superior (0.0 = perfect accuracy). Decision metrics (POD, FAR, CSI) are evaluated at standard decision threshold $p \ge 0.5$.*

---

## 10. Temporal & Station Analysis (R2 Calibrated)

### Monthly Breakdown (TEST Period)

| Threshold | Month | Records | Event Count | Observed Rate | Predicted Prob Mean | Brier Score |
|-----------|-------|---------|-------------|---------------|----------------------|-------------|
| **1.0 mm** | May 2024 | 744 | 77 | 10.35% | 0.95% | 0.102711 |
| **1.0 mm** | June 2024 | 720 | 88 | 12.22% | 0.95% | 0.120512 |
| **10.0 mm** | May 2024 | 744 | 4 | 0.54% | 0.00% | 0.005376 |
| **10.0 mm** | June 2024 | 720 | 2 | 0.28% | 0.00% | 0.002778 |

### Lead-Time Breakdown (TEST Period)

| Threshold | Lead Time | Records | Event Count | Observed Rate | Brier Score |
|-----------|-----------|---------|-------------|---------------|-------------|
| **1.0 mm** | 24h | 488 | 55 | 11.27% | 0.111467 |
| **1.0 mm** | 48h | 488 | 55 | 11.27% | 0.111467 |
| **1.0 mm** | 72h | 488 | 55 | 11.27% | 0.111467 |

---

## 11. Panchayat Spatial Aggregation

Grid-level probabilities across all 10,530 1-km grid cells in Coimbatore District were aggregated to each of the **180 Gram Panchayats**.

### Aggregation Schema
Outputs include:
- `panchayat_id`, `timestamp`, `lead_time`
- `rain_probability_1mm`, `rain_probability_10mm`, `rain_probability_25mm` (Mean cell probabilities)
- `rain_probability_1mm_p10`, `rain_probability_1mm_p90`
- `rain_probability_10mm_p10`, `rain_probability_10mm_p90`
- `rain_probability_25mm_p10`, `rain_probability_25mm_p90`
- `spatial_spread_1mm`, `spatial_spread_10mm`, `spatial_spread_25mm` (Standard deviation across grid cells)
- `grid_cell_count`
- `aggregation_status` (`"OK"` if `grid_cell_count >= 3`, else `"SUBGRID_RANGE_UNRESOLVED"`)

### Aggregation Summary

| Statistic | Value |
|-----------|-------|
| **Total Panchayat Forecast Records** | **32,940** |
| **Unique Panchayats Represented** | **180 / 180** |
| **Panchayats with Status = OK (>= 3 cells)** | **178** |
| **Panchayats with Status = SUBGRID_RANGE_UNRESOLVED (< 3 cells)** | **2** |

---

## 12. Explicit Limitations & Disclaimers

1. **Phase 1 Stand-in Forecasts**: The current forecast source relies on Phase 1 stand-in gridded weather forecasts. Performance metrics reflect this baseline.
2. **Seasonal Regime Shift**: Dry training months (Jan–Mar) contain minimal rainfall events (0.70%), whereas the TEST period (May–June) experiences monsoon onset (11.27% rainfall rate). This causes under-prediction of rainfall occurrence by ML models trained strictly on historical dry-season data.
3. **Panchayat Aggregation Context**: Panchayat probabilities represent spatial summaries derived from the model's 1-km downscaled grid, not direct rain gauge measurements at every individual field.
4. **No Claim of Nationwide Generalization**: Results are demonstrated exclusively for Coimbatore District pilot data.

---

## 13. Scientific Interpretation & Audit Findings

### Scientific Classifications
1. **R1 Logistic Regression Anomaly**: **Class C — Distribution Shift / Linear Extrapolation on Temporal Cyclical Features**. In TRAIN (Jan–Mar), cyclical sine/cosine day-of-year features learned negative weights due to sparse Q1 events. In TEST (May–June), negative feature values multiplied by negative weights created a positive logit shift, inflating predicted probabilities to $\approx 50\%$.
2. **R2 LightGBM Prior Compression**: **Class C — Distribution Shift**. LightGBM trees do not extrapolate linearly. Leaf probabilities remain bounded by the Q1 training event prior ($0.70\%$), predicting $p_{\text{mean}} = 0.0019$ on TEST.
3. **$\ge 10\text{ mm}$ Threshold**: **Class D — Insufficient Sample Size / Data-Limited**. With 0 events in TRAIN and 0 in CALIB, supervised models cannot learn non-zero decision boundaries.
4. **$\ge 25\text{ mm}$ Threshold**: **Not Evaluable / Unobserved**. Zero events exist across all 6 months of data.

---

## 14. File Artifacts Created / Modified

| File | Action | Description |
|------|--------|-------------|
| `configs/rainfall_config.yaml` | Created | Configuration file for Phase 6 |
| `src/ml/rainfall_data.py` | Created | Data audit, target creation, event rate summaries |
| `src/ml/rainfall_models.py` | Created | R0, R1, R2 raw, Isotonic Calibrator implementations |
| `src/ml/rainfall_evaluator.py` | Created | Brier score, POD, FAR, CSI, diagnostic breakdowns |
| `src/ml/panchayat_aggregator.py` | Created | 1-km grid prediction & Panchayat spatial aggregation |
| `scripts/build_phase6_rainfall.py` | Created | End-to-end Phase 6 execution pipeline runner |
| `tests/test_phase6_rainfall.py` | Created | 9 deterministic unit tests for Phase 6 |
| `docs/phase6_rainfall_results.md` | Created | This document |
| `data/processed/predictions/station_rainfall_predictions.csv` | Generated | Station-level predictions dataset |
| `data/processed/predictions/panchayat_rainfall_predictions.csv` | Generated | Panchayat-level aggregated predictions dataset (32,940 records) |
| `data/metadata/validation_phase6_rainfall.json` | Generated | Phase 6 metadata validation report |
