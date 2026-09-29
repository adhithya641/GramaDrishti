# GramDrishti - Phase 5 Audit Report

## Audit Summary

| Item | Status |
|------|--------|
| **Conformal Implementation** | VERIFIED |
| **Quantile Ordering** | VERIFIED |
| **Interval Construction** | VERIFIED |
| **Calibration Isolation** | VERIFIED |
| **Data Quality** | CLEAN |
| **Temperature UQ** | VERIFIED |
| **Humidity UQ** | PASS WITH LIMITATIONS |
| **Overall Audit Status** | **PASS WITH LIMITATIONS** |

---

## 1. Reproduction Verification

Phase 5 results are fully reproducible:

| Metric | Expected | Actual |
|--------|----------|--------|
| TRAIN records | 2,136 | 2,136 |
| CALIBRATION records | 720 | 720 |
| TEST records | 1,464 | 1,464 |
| Temperature conformal correction | 1.044 | 1.044165 |
| Humidity conformal correction | 3.802 | 3.802181 |
| Temperature CALIB coverage | 80.14% | 80.14% |
| Temperature TEST coverage | 87.70% | 87.70% |
| Humidity CALIB coverage | 80.14% | 80.14% |
| Humidity TEST coverage | 20.15% | 20.15% |

---

## 2. Conformal Implementation Audit

### Score Formula

```
E_i = max(q10_i - y_i, y_i - q90_i)
```

**Verification:** Manually computed with deterministic inputs `y = [1,2,3,4,5]`,
`q10 = [0.5, 1.5, 2.0, 3.0, 4.0]`, `q90 = [1.5, 2.5, 4.0, 5.0, 6.0]`.
Expected scores `[-0.5, -0.5, -1.0, -1.0, -1.0]` match function output exactly.

This is the standard Romano et al. (2019) CQR formulation. Scores CAN be negative
(when observation falls inside the raw interval). **No floor at 0 is required.**

### Finite-Sample Quantile

```
q_level = (1 - alpha) * (1 + 1/n)
correction = np.quantile(scores, min(q_level, 1.0), method='higher')
```

For `alpha = 0.2`, `n = 720`:
```
q_level = 0.8 * (1 + 1/720) = 0.80111
```

Verified against manual computation. **CORRECT.**

### Calibration Isolation

- Conformal scores computed from **720 calibration records** only
- TEST observations are **never** used to compute or adjust the correction
- **VERIFIED.**

### Interval Construction

```
lower = q10 - correction
upper = q90 + correction
```

Verified by spot-checking individual rows. **CORRECT.**

---

## 3. Quantile Ordering Audit

### Post-Enforcement (monotonic correction applied)

| Split | q10 > q50 crossings | q50 > q90 crossings |
|-------|---------------------|---------------------|
| CALIB temp | 0/720 (0.00%) | 0/720 (0.00%) |
| TEST temp | 0/1464 (0.00%) | 0/1464 (0.00%) |
| CALIB hum | 0/720 (0.00%) | 0/720 (0.00%) |
| TEST hum | 0/1464 (0.00%) | 0/1464 (0.00%) |

### Pre-Enforcement (raw quantile predictions)

| Split | q10 > q50 | q50 > q90 |
|-------|-----------|-----------|
| CALIB hum | 0/720 (0.00%) | 9/720 (1.25%) |
| TEST hum | 0/1464 (0.00%) | 10/1464 (0.68%) |

**Conclusion:** Minor raw crossings exist (< 1.3%), all corrected by monotonic enforcement.
Quantile crossing does NOT contribute materially to humidity undercoverage.

---

## 4. Interval Audit

### Coverage Comparison

| Split | Temp Raw | Temp CQR | Hum Raw | Hum CQR |
|-------|----------|----------|---------|---------|
| CALIBRATION | 44.31% | **80.14%** | 59.72% | **80.14%** |
| TEST | 60.59% | **87.70%** | 11.61% | **20.15%** |

### Humidity Interval Width Statistics

| Statistic | CALIB Raw | CALIB CQR | TEST Raw | TEST CQR |
|-----------|-----------|-----------|----------|----------|
| Mean | 26.71 | 34.31 | 20.04 | 27.64 |
| Median | 27.14 | 34.75 | 19.31 | 26.92 |
| P10 | 19.51 | 27.12 | 14.06 | 21.66 |
| P90 | 32.68 | 40.28 | 27.50 | 35.10 |
| Min | 12.20 | 19.81 | 7.55 | 15.15 |
| Max | 44.26 | 51.87 | 38.08 | 45.69 |

### Where TEST Observations Fall

| Position | Percentage |
|----------|------------|
| Below q10 | 0.41% |
| Inside interval | **20.15%** |
| Above q90 | **79.44%** |

**Critical finding:** 79.44% of TEST humidity observations exceed the CQR upper bound.
The intervals are not "too narrow" in an absolute sense (mean width = 27.64 pp);
the observations have shifted **systematically upward** beyond the interval range.

---

## 5. Residual Distribution Shift Analysis

### Humidity Residual (observed - B2) Statistics

| Statistic | TRAIN | CALIBRATION | TEST |
|-----------|-------|-------------|------|
| Mean | +4.42 | +6.50 | **+25.04** |
| Median | +4.41 | +9.46 | **+26.40** |
| Std | 15.44 | 17.22 | 12.13 |
| Min | -48.36 | -43.44 | -25.46 |
| Max | +53.75 | +52.33 | +61.57 |
| P10 | -15.48 | -20.10 | +9.52 |
| P90 | +24.72 | +26.54 | +39.04 |

### Verified Shift Magnitude

| Metric | Value |
|--------|-------|
| TEST mean - CALIB mean | **+18.534 pp** |
| TEST median - CALIB median | **+16.940 pp** |

The claimed ~+18.5 pp shift is **verified at +18.534 pp (mean)**.

### Temperature Residual Shift

| Statistic | TRAIN | CALIBRATION | TEST |
|-----------|-------|-------------|------|
| Mean | -1.73 | +0.76 | -1.40 |
| Std | 3.21 | 2.79 | 2.78 |

Temperature shift (TEST - CALIB mean): **-2.161 C** — moderate, and the wider CQR
interval absorbs it successfully (87.70% coverage).

---

## 6. Prediction Distribution Shift

### Humidity Predictions (Residual Space)

| Statistic | CALIB q10(raw) | CALIB q90(raw) | TEST q10(raw) | TEST q90(raw) |
|-----------|----------------|----------------|---------------|---------------|
| Mean | -12.10 | 14.61 | -5.74 | 14.30 |
| Median | -11.20 | 14.47 | -5.10 | 14.23 |

**Key insight:** The model's q10 predictions shift upward from CALIB to TEST
(from -12.10 to -5.74), indicating the model partially detects the change.
However, q90 barely moves (14.61 to 14.30). The model shifts the interval
location but does not widen it enough to match the +25 pp actual residual mean.

---

## 7. Coverage by Lead Time

| Lead Time | Split | N | Hum Raw | Hum CQR | Temp CQR | Hum Width |
|-----------|-------|---|---------|---------|----------|-----------|
| 24h | CALIB | 240 | 62.08% | **81.25%** | 81.25% | 34.51 |
| 24h | TEST | 488 | 11.07% | **21.93%** | 90.98% | 27.70 |
| 48h | CALIB | 240 | 60.83% | **79.58%** | 79.17% | 34.19 |
| 48h | TEST | 488 | 12.09% | **18.85%** | 85.66% | 27.61 |
| 72h | CALIB | 240 | 56.25% | **79.58%** | 80.00% | 34.23 |
| 72h | TEST | 488 | 11.68% | **19.67%** | 86.48% | 27.62 |

**Conclusion:** Humidity undercoverage is **uniform across all lead times** (19-22%).
No single lead time causes the failure. This confirms a global temporal shift, not
a lead-time-specific problem.

---

## 8. Coverage by Station

| Station | CALIB Hum CQR | TEST Hum CQR | TEST Hum Resid Mean |
|---------|---------------|--------------|---------------------|
| STN_CBE_01 | 76.67% | 16.39% | +25.57 |
| STN_CBE_02 | 86.67% | 13.11% | +26.86 |
| STN_CBE_03 | 95.56% | 15.30% | +22.84 |
| STN_CBE_04 | 55.56% | 28.42% | +17.34 |
| STN_CBE_05 | 85.56% | 32.24% | +21.46 |
| STN_CBE_06 | 66.67% | 33.33% | +29.27 |
| STN_CBE_07 | 92.22% | 8.20% | +29.68 |
| STN_CBE_08 | 82.22% | 14.21% | +27.26 |

**Conclusion:** Humidity undercoverage is **widespread across ALL 8 stations**.
Every station has TEST coverage below 34%. This is not a spatial outlier problem.

---

## 9. Coverage by Elevation Group

| Split | Group | N | Hum CQR | Temp CQR |
|-------|-------|---|---------|----------|
| CALIB | LOW_ELEV | 360 | 88.89% | 80.00% |
| CALIB | HIGH_ELEV | 360 | 71.39% | 80.28% |
| TEST | LOW_ELEV | 732 | 17.49% | 89.62% |
| TEST | HIGH_ELEV | 732 | 22.81% | 85.79% |

**Conclusion:** Both elevation groups fail similarly on TEST humidity. Elevation
does not explain the coverage degradation. The shift is temporal, not spatial.

---

## 10. Bias Analysis

| Metric | CALIB | TEST |
|--------|-------|------|
| Mean residual (obs-B2) | +6.50 | +25.04 |
| q50 prediction mean | 2.34 | 6.16 |
| q50 prediction error | -4.16 | **-18.88** |
| CQR midpoint error | -5.25 | **-20.75** |
| q50 MAE | 10.10 | 19.13 |

The model systematically **underpredicts** humidity residuals during TEST by
-18.88 pp on average. The CQR midpoint is -20.75 pp below the true residual.
This is a direct consequence of the +18.5 pp distribution shift.

---

## 11. Temporal Shift Analysis (Monthly)

| Month | N | Mean Residual | CQR Coverage | Width |
|-------|---|---------------|--------------|-------|
| April (CALIB) | 720 | +6.50 | **80.14%** | 34.31 |
| May (TEST) | 744 | +22.04 | **22.85%** | 27.78 |
| June (TEST) | 720 | +28.13 | **17.36%** | 27.50 |

**Key finding:** The shift does not appear suddenly — it progresses:
- April: +6.50 mean residual, 80.14% coverage
- May: +22.04 mean residual, 22.85% coverage
- June: +28.13 mean residual, 17.36% coverage

This is consistent with gradual monsoon onset increasing observed humidity
while the forecast (B2 baseline) fails to track the increase.

---

## 12. Data Quality Audit

| Check | Result |
|-------|--------|
| Duplicate (station, time, lead) | **0** |
| RH < 0 violations | **0** |
| RH > 100 violations | **0** |
| Missing observed_temperature | **0** |
| Missing observed_humidity | **0** |
| Missing b2_temperature | **0** |
| Missing b2_humidity | **0** |
| Missing forecast_temperature | **0** |
| Missing forecast_humidity | **0** |
| Unique stations | **8** |
| Unique grid_ids | **8** |

**All clean. No data quality issues found.**

---

## 13. Calibration vs TEST Comparison

### Humidity

| Metric | Calibration | TEST |
|--------|-------------|------|
| Records | 720 | 1,464 |
| CQR Coverage | **80.14%** | **20.15%** |
| Mean residual | +6.50 | +25.04 |
| Median residual | +9.46 | +26.40 |
| Residual std | 17.22 | 12.13 |
| q50 MAE | 10.10 | 19.13 |
| Mean interval width | 34.31 | 27.64 |
| Median interval width | 34.75 | 26.92 |

### Temperature

| Metric | Calibration | TEST |
|--------|-------------|------|
| Records | 720 | 1,464 |
| CQR Coverage | **80.14%** | **87.70%** |
| Mean residual | +0.76 | -1.40 |
| Median residual | +0.88 | -1.59 |
| Residual std | 2.79 | 2.78 |
| q50 MAE | 1.23 | 1.17 |
| Mean interval width | 4.65 | 4.73 |
| Median interval width | 4.35 | 4.61 |

---

## 14. Scientific Interpretation

### Root Cause Classification

**D — TEMPORAL DISTRIBUTION SHIFT**

### Evidence Chain

1. **Conformal implementation is mathematically correct** — manually verified with
   deterministic inputs, matching Romano et al. (2019) CQR formulation.

2. **Calibration coverage matches target** — both temperature (80.14%) and humidity
   (80.14%) achieve the 80% nominal coverage on the calibration split.

3. **No data quality issues** — zero duplicates, zero missing values, zero RH
   bound violations.

4. **No quantile ordering issues** — monotonic enforcement corrects < 1.3% of
   raw predictions; this is immaterial to coverage.

5. **Humidity residual shifts +18.534 pp from CALIB to TEST** — April mean
   residual = +6.50, May = +22.04, June = +28.13. This is a gradual, progressive
   shift consistent with Southwest Monsoon onset in Coimbatore.

6. **79.44% of TEST observations exceed the CQR upper bound** — the intervals
   are positioned correctly for the calibration distribution but the entire
   observation distribution has shifted upward.

7. **Undercoverage is uniform** across all 8 stations (8-33%), all 3 lead times
   (19-22%), and both elevation groups (17-23%).

8. **Temperature UQ transfers successfully** — the -2.16 C temperature residual
   shift is small relative to the 4.73 C interval width, resulting in 87.70%
   coverage.

### Statement

> The conformal calibration achieved approximately nominal coverage on the April
> calibration period but did not maintain that coverage on the May-June held-out
> period. This indicates that the calibration assumption (exchangeability) does
> not transfer reliably under the observed distribution shift.

> The humidity prediction interval should NOT be described as an 80% reliable
> operational interval during monsoon-onset periods without seasonal recalibration.

---

## 15. Items NOT Modified

Per audit requirements, the following were NOT changed:

- No recalibration using TEST data
- No interval widening to force TEST coverage
- No quantile model retuning on TEST
- No station removal
- No month removal
- No manual humidity interval shifting
- No TEST label alteration

---

## 17. Temperature Audit

| Check | Result |
|-------|--------|
| Calibration coverage | **80.14%** (target 80%) |
| TEST coverage | **87.70%** |
| Conformal correction | 1.044 C |
| Residual shift (TEST - CALIB) | -2.161 C |
| TEST below q10 | 3.07% |
| TEST above q90 | 9.22% |

Temperature UQ is **verified and operationally reliable**.

---

## Test Suite

**103/103 tests passing**

- 48 tests: Phase 1-3 ingestion/validation
- 27 tests: Phase 4 ML + audit
- 28 tests: Phase 5 UQ + audit

### Audit-Specific Tests Added

| Test | Purpose |
|------|---------|
| `test_conformal_score_formula_deterministic` | Manual score verification |
| `test_conformal_finite_sample_quantile` | Quantile index verification |
| `test_interval_construction_formula` | lower/upper construction |
| `test_calibration_isolation` | 720 calibration records only |
| `test_test_isolation` | 1464 TEST records never leak |
| `test_station_coverage_calculable` | Station breakdown validity |
| `test_lead_time_coverage_calculable` | Lead-time breakdown validity |
| `test_raw_observed_rh_bounds` | RH in [0, 100] |
| `test_conformal_correction_positive` | Finite correction values |
| `test_no_duplicate_records` | No data duplication |

---

## Files Changed

| File | Action |
|------|--------|
| `scripts/audit_phase5.py` | Created — comprehensive audit script |
| `tests/test_phase5_uncertainty.py` | Updated — 10 audit tests added |
| `docs/phase5_audit_report.md` | Created — this document |
| `docs/phase5_uncertainty_results.md` | Updated — audit section added |
