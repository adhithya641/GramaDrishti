# GramDrishti — Phase 9 SIH Demonstration Scenario
## Scripted Presentation Walkthrough & Juror Narrative

---

## Overview

This document outlines the step-by-step demonstration walkthrough for the Smart India Hackathon (SIH PS 26074) jury presentation. The narrative highlights GramDrishti's core value proposition: **validation-driven weather downscaling with honest uncertainty reporting and evidence-gated advisories.**

All demo scenes use historical replay predictions from the Coimbatore pilot region (180 Gram Panchayats, May 01 – June 30, 2024).

---

## Walkthrough Scenes

### Scene 1 — District Overview & Multi-Scale Grid
* **Visual**: Main Leaflet map displaying 180 Gram Panchayat polygon boundaries across 12 blocks in Coimbatore District.
* **Juror Narrative**:
  > *"Operational weather forecasts are emitted on coarse 10 km to 25 km global grid cells. GramDrishti ingests these coarse forecasts alongside high-resolution DEM terrain, land-cover, and hydrological features to downscale forecasts to 10,530 one-kilometre metric grid cells, aggregated up to all 180 Gram Panchayats in Coimbatore District."*

### Scene 2 — Panchayat Selection & Sub-Grid Range
* **Action**: Click on Gram Panchayat `Anaimalai Panchayat 1` (`GP_33_12_0001`).
* **Visual**: Panchayat Detail panel populates with location metadata:
  * Panchayat: `Anaimalai Panchayat 1`
  * Block: `Anaimalai`
  * Sub-grid Cells: `9 cells (OK)`
* **Juror Narrative**:
  > *"Every Gram Panchayat's spatial extent is tracked explicitly. When a Panchayat contains at least 3 grid cells, we compute exact spatial range and mean bounds. Small Panchayats with fewer than 3 cells preserve a `SUBGRID_RANGE_UNRESOLVED` flag to prevent artificial precision."*

### Scene 3 — Coarse District Forecast vs Downscaled Panchayat Output
* **Visual**: Block vs Panchayat Downscaling card showing:
  * Coarse District Forecast: `32.40 °C` (ECMWF IFS Stand-in)
  * Downscaled Panchayats in Anaimalai Block: `30.80 °C` to `34.00 °C`
  * Label: `Historical replay / model output`
* **Juror Narrative**:
  > *"Notice how the coarse model predicts a uniform 32.4°C across the entire district. GramDrishti captures elevation lapse rates and terrain microclimates, revealing that Anaimalai Panchayat 1 is 30.8°C while neighboring valley Panchayats reach 34.0°C. This spatial variation is critical for agricultural planning."*

### Scene 4 — Calibrated Uncertainty Quantification (CQR)
* **Visual**: Uncertainty card displaying conformal quantile interval bounds:
  * Temperature: P10 (`30.04°C`) ── P50 (`32.40°C`) ── P90 (`34.76°C`), Interval Width `4.73°C`.
  * Humidity: P10 (`54.70%`) ── P50 (`68.50%`) ── P90 (`82.30%`), Interval Width `27.61%`.
* **Juror Narrative**:
  > *"We do not present point predictions alone. GramDrishti applies Conformalized Quantile Regression (CQR) to provide 80% empirical coverage guarantees. Temperature intervals achieve 87.70% test coverage with a narrow 4.73°C width."*

### Scene 5 — Reliability Engine & Transparent Uncertainty
* **Visual**: Reliability badges and warning box:
  * Temperature Reliability: `HIGH`
  * Humidity Reliability: `LOW`
  * Warning Box: `⚠️ LOW RELIABILITY — temporal distribution shift detected`
* **Juror Narrative**:
  > *"Here is GramDrishti's most critical scientific innovation: when a model degrades, we do NOT hide it. During the Q1 dry to Q2 monsoon transition, humidity test coverage dropped to 20.15%. Our rule engine automatically flags humidity as LOW reliability with machine-readable reason code `CQR_TEST_COVERAGE_BELOW_TARGET`."*

### Scene 6 — Evidence-Based Fallback Hierarchy
* **Visual**: Fallback Source badge: `BASELINE_B2` / `PRIMARY_MODEL` / `NONE_NOT_EVALUABLE`.
* **Juror Narrative**:
  > *"When primary ML predictions fail reliability gates, GramDrishti automatically activates physical fallback to lapse-rate physical baselines (`BASELINE_B2`). For heavy rainfall (≥10mm and ≥25mm) where historical training events were zero, we return `NOT_EVALUABLE` and fabricate ZERO artificial probabilities."*

### Scene 7 — Evidence-Gated Crop Advisories
* **Visual**: Agro-Advisory card displaying:
  * Temperature Advisory: `ACTIONABLE` — *"Optimal temperature for crop growth."*
  * Humidity Advisory: `CAUTIONARY` — *"CAUTION (CQR_TEST_COVERAGE_BELOW_TARGET): Monitor humidity for fungal pests."*
  * Heavy Rain Advisory: `BLOCKED` — *"Insufficient validated evidence for this condition at this location/time."*
* **Juror Narrative**:
  > *"Crop advisories are strictly gated. Reliable forecasts generate actionable advice; low-reliability forecasts emit cautionary warnings; unevaluable or expired forecasts block actionable advisories entirely."*

### Scene 8 — Rigorous Empirical Scientific Evidence
* **Visual**: System Status Matrix & Validation Metrics Summary:
  * Temperature MAE: Coarse B0 = `2.3165°C` → ML Model A = `1.0823°C` (53.3% improvement).
  * Humidity MAE: Coarse B0 = `25.5342%` → ML Model B Full GIS = `19.4556%`.
  * GIS Finding: GIS terrain features improved humidity but did **not** improve temperature over Forecast+Time Model A (`1.0823°C` vs `1.2225°C`).
* **Juror Narrative**:
  > *"GramDrishti is fully backed by rigorous held-out test evaluation across 4,320 matched pairs. We report our true empirical results without overclaiming."*
