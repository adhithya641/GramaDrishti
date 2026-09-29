# Phase 3 Weather Matchup & Baseline Methodology
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

## 1. Temporal Matching Procedure

* **Matching Rule:** Deterministic full datetime matching where `observation_time == valid_time`. Matching by date alone is strictly prohibited.
* **Preserved Metadata:** `forecast_issue_time`, `valid_time`, `lead_time_hours` (24h, 48h, 72h).
* **Data Provenance:** Historical forecast dataset status is **STAND-IN** (sourced from Open-Meteo operational model run archives, ECMWF IFS / GFS).

---

## 2. Spatial Alignment & Station Grouping

* **Spatial Mapping:** Each ground weather station `station_id` is mapped to:
  1. Nearest 1 km projected metric grid cell (`grid_id`) from Phase 2.
  2. Assigned Gram Panchayat (`panchayat_id`).
  3. Parent coarse forecast grid point (`forecast_parent_id`).
  4. Surrounding 4 coarse forecast grid points ($P_{00}, P_{10}, P_{01}, P_{11}$) for bilinear interpolation.
* **Leakage Prevention:** `station_id` is strictly an observational grouping key and must **never** be used as a numerical feature in machine learning models.
* **Station Grouping for LOSO:** `station_group` assigned (`GROUP_STN_CBE_01` ...) to facilitate Leave-One-Station-Out (LOSO) cross-validation in future phases.

---

## 3. Observation QC Policy & Target Definitions

* **Target Truth Policy:**
  * `VALID` observations: Primary target truth for baseline evaluation.
  * `SUSPICIOUS` observations: Preserved and flagged (included with warnings).
  * `INVALID` observations: Excluded from baseline evaluation truth.
* **Target Variables:**
  * `observed_temperature` (°C)
  * `observed_humidity` (%)
  * `observed_rainfall` (mm)

---

## 4. Baseline Forecasting Ladder (B0, B1, B2, B3)

### **B0 — Coarse Forecast Baseline**
* **Formulation:** $B0_{\text{temp}} = \text{forecast\_temperature}$, $B0_{\text{hum}} = \text{forecast\_humidity}$, $B0_{\text{rain}} = \text{forecast\_rainfall}$.
* **Meaning:** Assigns the coarse parent forecast value directly to the observation location without any spatial refinement.

### **B1 — Bilinear Interpolation Baseline**
* **Formulation:** 2D bilinear interpolation from 4 surrounding forecast grid points:
  $$B1(x,y) = (1-u)(1-v) f_{00} + u(1-v) f_{10} + (1-u)v f_{01} + uv f_{11}$$
* **Fallback Policy:** If 4 surrounding points are unavailable or on grid boundaries, `b1_status` is recorded as `FALLBACK_B0` and explicitly falls back to B0.

### **B2 — Elevation / Environmental Lapse-Rate Correction Baseline**
* **Temperature Formulation:**
  $$B2_{\text{temp}} = \text{forecast\_temperature} + \gamma_{\text{lapse}} \times (z_{\text{station}} - z_{\text{grid}})$$
  where $\gamma_{\text{lapse}} = -0.0065\text{ °C/m}$ (-6.5 °C per 1,000m).
* **Humidity Note:** Relative humidity lapse rate is physically non-linear and unjustified without dewpoint/vapor pressure thermodynamic equations; $B2_{\text{humidity}}$ is left equal to B0 with explicit physical documentation.

### **B3 — Quantile Mapping Baseline**
* **Formulation:** Empirical quantile mapping bias correction mapping forecast quantiles to observed quantiles:
  $$B3(f) = Q_{\text{obs}}\left(Q_{\text{fc}}^{-1}(f)\right)$$
* **Leakage Prevention:** Fitted **strictly** on the `TRAIN` split (`2024-01-01` to `2024-03-31`) across 100 quantiles and applied to `CALIBRATION` and `TEST` splits.

---

## 5. Chronological Temporal Splitting

No random splitting of weather records. Partitioned deterministically by timestamp:

| Split | Date Range | Record Count | Description |
| :--- | :--- | :--- | :--- |
| **TRAIN** | `2024-01-01` to `2024-03-31` | 2,136 | Calibration and quantile mapping fitting period |
| **CALIBRATION** | `2024-04-01` to `2024-04-30` | 720 | Interim hyperparameter tuning period |
| **TEST** | `2024-05-01` to `2024-06-30` | 1,464 | Final out-of-time evaluation test period |

---

## 6. Scientific Caution & Disclaimer

* **No Performance Claims:** Baseline evaluations provide initial descriptive benchmarks only. No claim is made that "AI improves weather forecasts" or that "B2/B3 is superior" at this stage.
* **Future Evaluation:** Full evaluation of downscaling skill will be performed in Phase 4 using held-out stations and test time periods.
