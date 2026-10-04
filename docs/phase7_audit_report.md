# GramDrishti — Phase 7 Scientific & Codebase Audit Report
## Reliability, Confidence & Fallback Layer Audit

---

## Audit Executive Summary

| Component / Logic | Audit Status | Key Evidence / Metric |
|---|---|---|
| **Reliability Logic** | **VERIFIED** | Rule-based engine correctly downgrades confidence based on Phase 4/5/6 held-out test metrics. |
| **Humidity Reliability** | **VERIFIED LOW** | Conformal test coverage = 20.15% (< 70% threshold) due to monsoon distribution shift. Flagged `LOW` with `CQR_TEST_COVERAGE_BELOW_TARGET`. |
| **Rainfall ≥ 1 mm** | **VERIFIED MEDIUM** | Train event rate 0.70% → Test event rate 11.27%. Flagged `MEDIUM` with `TEMPORAL_DISTRIBUTION_SHIFT_DETECTED`. |
| **Rainfall ≥ 10 mm** | **VERIFIED NOT_EVALUABLE** | Train events = 0, Calib events = 0, Test events = 6. Flagged `NOT_EVALUABLE` with `INSUFFICIENT_TRAINING_EVENTS`. |
| **Rainfall ≥ 25 mm** | **VERIFIED NOT_EVALUABLE** | Train events = 0, Calib events = 0, Test events = 0. Flagged `NOT_EVALUABLE` with `NO_POSITIVE_EVENTS_IN_TRAIN`. |
| **Freshness Logic** | **VERIFIED** | Tracks `data_age_hours` and labels `FRESH` (≤24h), `AGING` (24–48h), `EXPIRED` (>48h). Expired status blocks advisories. |
| **Fallback Hierarchy** | **VERIFIED** | Falls back to B2/B3 physical baselines when primary model is unreliable. **Zero false probabilities fabricated for unevaluable classes.** |
| **Advisory Gating** | **VERIFIED** | Blocks actionable crop advisories on `NOT_EVALUABLE` or `EXPIRED` forecasts. Displays honest caution messages on `LOW`. |
| **Panchayat Aggregation** | **VERIFIED** | Aggregates 1-km cell predictions; preserves `SUBGRID_RANGE_UNRESOLVED` flag when grid cell count < 3. |
| **Overall Phase 7 Audit Status** | **PASS WITH LIMITATIONS** | The system is designed to provide transparent uncertainty reporting and avoid unsupported precision. |

---

## 1. Implementation & Evidence Verification

Phase 7 decisions are driven strictly by canonical held-out test metrics from Phases 4, 5, and 6:

```text
                        ┌─────────────────────────────────────┐
                        │  Phase 4/5/6 Validation Evidence     │
                        └─────────────────────────────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
│   Temperature   │               │    Humidity     │               │    Rainfall     │
│ MAE = 1.22°C    │               │ MAE = 19.46%    │               │ ≥1mm: 165 test  │
│ CQR Cov = 87.7% │               │ CQR Cov = 20.15%│               │ ≥10mm: 0 train  │
│ Width = 4.73°C  │               │ Shift = +18.53  │               │ ≥25mm: 0 events │
└─────────────────┘               └─────────────────┘               └─────────────────┘
         │                                 │                                 │
         ▼                                 ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐               ┌─────────────────┐
│ Confidence: HIGH│               │ Confidence: LOW │               │ ≥1mm: MEDIUM    │
│ Reasons: None   │               │ Reasons:        │               │ ≥10mm: NOT_EVAL │
│                 │               │ CQR_TEST_COVER  │               │ ≥25mm: NOT_EVAL │
└─────────────────┘               └─────────────────┘               └─────────────────┘
```

### Direct Empirical Linkage:
1. **Temperature**: Held-out test coverage of 87.70% satisfies the 80% conformal target. Interval width (4.73°C) is within acceptable bounds (<6.0°C). Result: `HIGH` confidence.
2. **Humidity**: Calibration set coverage was 80.14%, but test coverage dropped severely to **20.15%** due to monsoon onset shift (residual mean shift +18.53%). Result: `LOW` confidence with `CQR_TEST_COVERAGE_BELOW_TARGET` and `TEMPORAL_DISTRIBUTION_SHIFT_DETECTED`.
3. **Rainfall ≥ 10 mm & ≥ 25 mm**: Supervised training split contained 0 positive events in TRAIN and 0 in CALIB. Result: `NOT_EVALUABLE`.

---

## 2. Fallback & Freshness Audit

### Fallback Rules:
- Primary ML prediction is evaluated against the reliability gate.
- When primary ML is `LOW` or `EXPIRED`, the system activates fallback to `BASELINE_B2` (physical forecast) or `BASELINE_B3` (linear regression).
- **CRITICAL AUDIT ITEM**: For `NOT_EVALUABLE` rainfall thresholds (≥10mm, ≥25mm), `fallback_used` is `false`, `source` is `"NONE_NOT_EVALUABLE"`, and `selected_value` is `null`. The system **does not fabricate artificial fallback probabilities**.

### Freshness Metadata:
- `FRESH`: `data_age_hours` ≤ 24.0h. Eligible for actionable advisory.
- `AGING`: 24.0h < `data_age_hours` ≤ 48.0h. Eligible with warning.
- `EXPIRED`: `data_age_hours` > 48.0h. Advisory blocked.

---

## 3. Advisory Gating Verification

The advisory engine uses explicit conditional gating:
- **`ACTIONABLE`**: Standard crop advisory emitted for `HIGH` or `MEDIUM` confidence forecasts.
- **`CAUTIONARY`**: Cautionary notice emitted for `LOW` confidence forecasts (e.g., humidity).
- **`BLOCKED`**: Actionable advisory blocked when confidence is `NOT_EVALUABLE` or forecast is `EXPIRED`. Returns:
  `"Insufficient validated evidence for this condition at this location/time."`

---

## 4. Documented Scientific Limitations

The following scientific limitations must remain visible across all project artifacts:

1. **Forecast Stand-in Limitation**: Matchup dataset uses global reanalysis/forecast proxies for ground truth alignment.
2. **Pilot Region Scope**: System is validated on Coimbatore District (180 Gram Panchayats). Results cannot be claimed for nationwide deployment without retraining.
3. **Seasonal Distribution Shift**: Historical split transitions from dry Q1 (TRAIN) to monsoon onset Q2 (TEST). Humidity residual mean shifts from +4.42 to +25.03.
4. **Humidity CQR Undercoverage**: Test CQR coverage (20.15%) reflects temporal shift and forces `LOW` reliability status.
5. **Rainfall Scarcity**: ≥10 mm and ≥25 mm thresholds are data-limited/unevaluable under the historical split.
6. **1 km Grid Representation**: 1-km grid downscaling represents spatial resolution, not guaranteed point-level microclimate accuracy.
7. **No Guaranteed Uncertainty Bounds**: Conformal guarantees apply under i.i.d. conditions; distribution shift degrades coverage as documented.

---

## 5. Claims Audit

The system explicitly verifies and enforces that NO unsupported scientific claims are made:

- **CLAIM REJECTED**: "AI model is always superior to physical baselines."
  - *Fact*: Machine learning model predictions are downgraded to `LOW` or fallback to baselines whenever held-out coverage or accuracy degrades.
- **CLAIM REJECTED**: "Terrain features always improve temperature accuracy."
  - *Fact*: Improvements are verified empirically on test sets; unverified gains are not assumed.
- **CLAIM REJECTED**: "Rainfall probabilities are highly reliable for heavy rain events."
  - *Fact*: Heavy rain thresholds (≥10mm, ≥25mm) are explicitly labeled `NOT_EVALUABLE`.
- **CLAIM REJECTED**: "Uncertainty intervals guarantee 80% coverage under all conditions."
  - *Fact*: Test coverage for humidity drops to 20.15% under temporal shift, which is reported transparently.
- **CLAIM REJECTED**: "1 km grid predictions represent exact ground truth."
  - *Fact*: Downscaling provides gridded estimates subject to spatial and subgrid uncertainty.
- **CLAIM REJECTED**: "Model demonstrates nationwide generalization."
  - *Fact*: System scope is restricted to the pilot study region.
