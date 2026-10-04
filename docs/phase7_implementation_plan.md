# GramDrishti — Phase 7: Implementation Plan
## Reliability, Confidence & Fallback Layer

---

## Executive Summary

Phase 7 builds an explicit, transparent, evidence-based **Reliability, Confidence & Fallback Layer** for GramDrishti. The primary objective is to evaluate whether any model prediction can be trusted sufficiently to serve as an actionable panchayat-level forecast, without manufacturing artificial confidence.

This document outlines the design, schema, rules, fallback hierarchy, and audit criteria for Phase 7 implementation while fully preserving Phase 1–6 implementations, canonical metrics, and documented scientific limitations.

---

## 1. Existing System Inputs & Verification Evidence

Phase 7 ingests outputs and validation metrics directly from previous phases:

| Input Variable / Dimension | Phase Source | Empirical Evidence / Metric | Operational Status |
|---|---|---|---|
| **Temperature Prediction** | Phase 4 (`ml_temperature`) | TEST MAE = 1.22°C, RMSE = 1.58°C, Bias = -0.08°C | Validated ML model |
| **Temperature UQ** | Phase 5 (`q10`, `q50`, `q90`, CQR) | TEST CQR Coverage = 87.70%, Mean Width = 4.73°C | Sufficient Coverage |
| **Humidity Prediction** | Phase 4 (`ml_humidity`) | TEST MAE = 19.46%, RMSE = 23.12%, Bias = +25.03% | Validated ML model |
| **Humidity UQ** | Phase 5 (`q10`, `q50`, `q90`, CQR) | TEST CQR Coverage = 20.15%, Mean Width = 27.61% | **Severe Undercoverage / Shift** |
| **Rainfall ≥ 1 mm** | Phase 6 (`prob_1mm`, LightGBM) | TRAIN Event Rate = 0.70% → TEST Event Rate = 11.27% | **Temporal Distribution Shift** |
| **Rainfall ≥ 10 mm** | Phase 6 (`prob_10mm`) | TRAIN = 0, CALIB = 0, TEST = 6 positive events | **Data Limited** |
| **Rainfall ≥ 25 mm** | Phase 6 (`prob_25mm`) | TRAIN = 0, CALIB = 0, TEST = 0 positive events | **Unevaluable (`NOT_EVALUABLE`)** |
| **Panchayat Grid Assignment** | Phase 2 / Phase 6 | 180 Panchayats, 10,530 cells; cell count per panchayat | `OK` (≥3 cells) / `SUBGRID_RANGE_UNRESOLVED` (<3 cells) |

---

## 2. Proposed Reliability Logic & Rules

Reliability is calculated deterministically through a rule engine:

```text
[ Prediction Inputs & Validation Metrics ]
                     ↓
[ Freshness Evaluator ] ──(Expired?)──> CONFIDENCE: EXPIRED / UNAVAILABLE
                     ↓
[ Uncertainty & Data Sufficiency Rules ]
                     ↓
┌──────────────────────────────────────────────────────────┐
│  - Humidity CQR coverage (20.15% < 80%) → LOW            │
│  - Rain ≥10mm (0 Train/Calib events) → NOT_EVALUABLE    │
│  - Rain ≥25mm (0 Events all splits) → NOT_EVALUABLE     │
│  - Subgrid cell count < 3 → SUBGRID_RANGE_UNRESOLVED     │
└──────────────────────────────────────────────────────────┘
                     ↓
[ Confidence Classification: HIGH | MEDIUM | LOW | NOT_EVALUABLE ]
```

### Configurable Thresholds (`[DESIGN]`)

Configurable parameters are declared in `configs/reliability_config.yaml`:
- `[DESIGN]` `temperature_max_interval_width`: 6.0°C (Width > 6.0°C downgrades to LOW)
- `[DESIGN]` `humidity_min_coverage`: 0.70 (Coverage < 0.70 downgrades to LOW)
- `[DESIGN]` `rain_10mm_min_train_events`: 10 (Train events < 10 marks `NOT_EVALUABLE`)
- `[DESIGN]` `rain_25mm_min_train_events`: 10 (Train events < 10 marks `NOT_EVALUABLE`)
- `[DESIGN]` `freshness_max_age_hours`: 48.0 hours

---

## 3. Evidence-Based Reason Codes

Every prediction evaluation outputs deterministic machine-readable reason strings:

| Code | Description | Trigger Condition |
|---|---|---|
| `CQR_TEST_COVERAGE_BELOW_TARGET` | Conformal interval test coverage is below target | Test coverage < `min_coverage` (e.g., Humidity 20.15%) |
| `TEMPORAL_DISTRIBUTION_SHIFT_DETECTED` | Significant distribution shift between train/calib and test | Event rate or residual mean shift detected across splits |
| `INSUFFICIENT_TRAINING_EVENTS` | Category or threshold lacks required training events | Train events < minimum required (e.g., Rain ≥10mm) |
| `NO_POSITIVE_EVENTS_IN_TRAIN` | Zero positive events in training set | Train positive count == 0 |
| `NO_POSITIVE_EVENTS_IN_CALIBRATION` | Zero positive events in calibration set | Calib positive count == 0 |
| `NO_POSITIVE_EVENTS_IN_TEST` | Zero positive events in test set | Test positive count == 0 |
| `INTERVAL_WIDTH_EXCEEDS_MAX` | Prediction uncertainty interval exceeds acceptable max | Interval width > max configured threshold |
| `SUBGRID_RANGE_UNRESOLVED` | Fewer than 3 grid cells available for panchayat aggregation | Grid cell count < 3 |
| `FORECAST_EXPIRED` | Forecast timestamp exceeds maximum validity window | Data age > max age hours |

---

## 4. Fallback Hierarchy

```text
               [ AI Prediction ]
                       ↓
              [ Reliability Check ]
                       ↓
             ┌─────────┴─────────┐
         [ Reliable ]       [ Unreliable ]
             ↓                   ↓
      (Show AI Output)    [ Select Fallback ]
                                 ↓
                     ┌───────────┴───────────┐
             [ Best Baseline ]        [ Coarse Forecast ]
             (e.g., B2/B3 Temp)       (District Average)
                     ↓                       ↓
             [ Still Unreliable / Expired / Not Evaluable ]
                                 ↓
                     [ NO ACTIONABLE FORECAST ]
```

### Fallback Rules:
1. **Temperature / Humidity**: If primary LightGBM residual model is unreliable or unavailable, fallback to best validated baseline (e.g., B2 physical forecast or B3 linear regression) if validated, else coarse/unavailable.
2. **Rainfall Rare Thresholds (≥10mm, ≥25mm)**: Since 0 events exist in training, **NO fallback probability is fabricated**. The system returns `NOT_EVALUABLE` and `fallback_used: false` with explicit notice.

---

## 5. Freshness & Advisory Gating Logic

### Freshness Metadata:
- `generated_at`: ISO timestamp of model run / forecast generation
- `valid_time`: ISO target forecast timestamp
- `data_age_hours`: Hours elapsed since `valid_time` relative to reference execution time
- `valid_until`: ISO timestamp when forecast expires
- `freshness_status`: `FRESH` (≤24h), `AGING` (24–48h), `EXPIRED` (>48h), `UNAVAILABLE` (missing time metadata)

### Advisory Gating:
- **`HIGH` / `MEDIUM` Confidence**: Normal weather advisory generated based on crop rules.
- **`LOW` Confidence**: Cautionary informational advisory generated (prefixed with caution notice).
- **`NOT_EVALUABLE` or `EXPIRED`**: Advisory engine **blocks actionable crop advice**, returning:
  `"Insufficient validated evidence for this condition at this location/time."`

---

## 6. Output Schema & API Specifications

API Endpoints:
- `GET /panchayat/{id}/reliability`
- `GET /panchayat/{id}/forecast`
- `GET /panchayat/{id}/advisory`

Example Aggregated Panchayat Reliability Response:
```json
{
  "panchayat_id": "TN_CBE_GP_001",
  "forecast": {
    "temperature": 32.4,
    "humidity": 68.5,
    "lead_time": 24
  },
  "uncertainty": {
    "temperature_p10": 30.1,
    "temperature_p90": 34.8,
    "temperature_interval_width": 4.7,
    "humidity_p10": 54.2,
    "humidity_p90": 82.8,
    "humidity_interval_width": 28.6
  },
  "rainfall_probability": {
    "rain_1mm": 0.112,
    "rain_10mm": null,
    "rain_25mm": null
  },
  "reliability": {
    "overall": "MEDIUM",
    "temperature": "MEDIUM",
    "humidity": "LOW",
    "rain_1mm": "MEDIUM",
    "rain_10mm": "NOT_EVALUABLE",
    "rain_25mm": "NOT_EVALUABLE"
  },
  "reasons": {
    "humidity": ["CQR_TEST_COVERAGE_BELOW_TARGET", "TEMPORAL_DISTRIBUTION_SHIFT_DETECTED"],
    "rain_10mm": ["INSUFFICIENT_TRAINING_EVENTS", "INSUFFICIENT_CALIBRATION_EVENTS"],
    "rain_25mm": ["NO_POSITIVE_EVENTS_IN_TRAIN", "NO_POSITIVE_EVENTS_IN_CALIBRATION", "NO_POSITIVE_EVENTS_IN_TEST"]
  },
  "freshness": {
    "status": "FRESH",
    "data_age_hours": 12.0
  },
  "fallback": {
    "used": false,
    "source": "PRIMARY_MODEL"
  }
}
```

---

## 7. Known Scientific Limitations

1. **Humidity Undercoverage**: Humidity CQR test coverage (20.15%) cannot support HIGH confidence predictions due to monsoon onset temporal distribution shift.
2. **Rainfall Data Scarcity**: Heavy rainfall (≥10mm and ≥25mm) lacks sufficient historical positive instances in the pilot dataset for supervised probability estimation.
3. **Spatial Scope**: Validated specifically on the Coimbatore pilot dataset (180 Gram Panchayats). Not extrapolated nationwide without retraining and recalibration.
4. **Transparent Uncertainty**: The system is designed to provide transparent uncertainty reporting and avoid unsupported precision.
