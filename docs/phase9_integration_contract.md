# GramDrishti — Phase 9 Integration Contract
## Data Flow, Artifact Interfaces & Component Pipeline

---

## 1. Executive Summary

Phase 9 establishes an explicit, transparent, end-to-end integration contract linking all dataset artifacts and processing modules produced across Phases 1–8 into a unified, SIH-demo-ready application.

The pipeline architecture preserves all Phase 1–8 scientific metrics, uncertainty calibrations, reliability rule classifications, and fallback rules without alteration.

---

## 2. End-to-End Data Pipeline Flow

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             INPUT DATA ARTIFACTS                                 │
│  - Coarse Forecasts (Open-Meteo ECMWF/GFS) & Station Observations (IMD/NOAA)    │
│  - Terrain/GIS Grid (10,530 1-km cells, EPSG:32643 DEM/LULC/Hydro)              │
│  - Panchayat Boundaries (180 Gram Panchayats, Coimbatore District)              │
└──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      PREDICTION & UNCERTAINTY LAYER                             │
│  - Phase 4 ML Models (LightGBM Residual Correction, Temperature & Humidity)      │
│  - Phase 5 UQ Engine (Conformalized Quantile Regression, P10 / P50 / P90)        │
│  - Phase 6 Rainfall Engine (LightGBM & Isotonic Calibration, ≥1mm/≥10mm/≥25mm)   │
└──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      RELIABILITY & FALLBACK GATING LAYER                         │
│  - Reliability Evaluator (Freshness, CQR Coverage, Event Sufficiency)            │
│  - Fallback Handler (Primary ML -> B2 Lapse Rate -> B3 Quantile -> Coarse)       │
│  - Advisory Gating Engine (ACTIONABLE -> CAUTIONARY -> BLOCKED)                 │
│  - Panchayat Aggregator (1-km to GP scale, preserving SUBGRID status)            │
└──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   DASHBOARD & REST API SERVICE LAYER                             │
│  - DashboardDataService (src/dashboard/service.py)                               │
│  - FastAPI Application Server (src/dashboard/app.py)                             │
│  - Single-Page Interactive Web Dashboard (src/dashboard/static/index.html)       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Component Contracts & Interfaces

### Contract 1: Ingestion & Geospatial Grid → Downscaling Models
* **Input Artifact**: `data/processed/geospatial/grid_1km.csv` (10,530 rows, elevation, slope, aspect, distance to coast/water).
* **Processing Module**: `src/ml/feature_builder.py` & `src/ml/trainer.py` (Phase 4).
* **Output Artifact**: `data/processed/predictions/weather_predictions.csv` (Point residual predictions `ml_temperature`, `ml_humidity`).
* **Next Component**: Uncertainty & Conformal Calibration (Phase 5).

### Contract 2: Residual Predictions → Uncertainty Quantification
* **Input Artifact**: `data/processed/predictions/weather_predictions.csv` & `data/metadata/validation_phase4_ml.json`.
* **Processing Module**: `src/uncertainty/cqr.py` & `src/uncertainty/evaluator.py` (Phase 5).
* **Output Artifact**: `data/processed/predictions/uncertainty_predictions.csv` (Quantiles `q10`, `q50`, `q90` and interval width).
* **Next Component**: Rainfall Probability Estimation (Phase 6).

### Contract 3: Matchups & Forecast Grid → Rainfall Probability Estimation
* **Input Artifact**: `data/processed/matchups/matchup_master.csv` & `configs/rainfall_config.yaml`.
* **Processing Module**: `src/ml/rainfall_models.py` & `src/ml/rainfall_evaluator.py` (Phase 6).
* **Output Artifact**: `data/processed/predictions/panchayat_rainfall_predictions.csv` (`prob_1mm`, `prob_10mm`, `prob_25mm`).
* **Next Component**: Reliability, Confidence & Fallback Evaluation (Phase 7).

### Contract 4: Multi-Variable Predictions → Evidence-Based Reliability Classification
* **Input Artifact**: `data/processed/predictions/panchayat_rainfall_predictions.csv` & `configs/reliability_config.yaml`.
* **Processing Module**: `src/reliability/evaluator.py` & `src/reliability/fallback.py` (Phase 7).
* **Rules & Classifications**:
  * **Temperature**: Held-out CQR coverage 87.70% (≥70% target) → `HIGH` / `MEDIUM` confidence.
  * **Humidity**: Held-out CQR coverage 20.15% (<70% target due to temporal shift) → `LOW` confidence with `CQR_TEST_COVERAGE_BELOW_TARGET` reason.
  * **Rainfall ≥ 1 mm**: Train 0.70% → Test 11.27% event rate → `MEDIUM` confidence with `TEMPORAL_DISTRIBUTION_SHIFT_DETECTED`.
  * **Rainfall ≥ 10 mm**: 0 Train, 0 Calib, 6 Test events → `NOT_EVALUABLE` confidence with `INSUFFICIENT_TRAINING_EVENTS`.
  * **Rainfall ≥ 25 mm**: 0 Train, 0 Calib, 0 Test events → `NOT_EVALUABLE` confidence with `NO_POSITIVE_EVENTS_IN_TRAIN`.
* **Output Artifact**: `data/processed/predictions/panchayat_reliability.csv` (32,940 records across 180 Gram Panchayats).
* **Next Component**: Dashboard & REST API Service Layer (Phase 8 & 9).

### Contract 5: Panchayat Reliability CSV + GeoJSON → API & UI Layer
* **Input Artifacts**: `data/processed/predictions/panchayat_reliability.csv` & `data/processed/boundaries/coimbatore_panchayats_processed.geojson`.
* **Processing Module**: `src/dashboard/service.py` & `src/dashboard/app.py` (Phases 8 & 9).
* **API Endpoints**:
  * `GET /api/v1/system-status`
  * `GET /api/v1/metadata`
  * `GET /api/v1/timestamps`
  * `GET /api/v1/panchayats`
  * `GET /api/v1/geojson`
  * `GET /panchayat/{id}/forecast`
  * `GET /panchayat/{id}/reliability`
  * `GET /panchayat/{id}/advisory`
  * `GET /api/v1/block-comparison`
* **Output Interface**: `src/dashboard/static/index.html` (Interactive Single-Page Application).

---

## 4. Operational & Scientific Invariants

1. **Monotonicity**: $P10 \le P50 \le P90$ across all valid temperature and humidity predictions.
2. **Zero Fabricated Probabilities**: `rain_probability_10mm` and `rain_probability_25mm` are `null` / `NaN` for all records.
3. **Spatial Preservation**: Panchayats with <3 grid cells maintain `SUBGRID_RANGE_UNRESOLVED` status (366 records).
4. **Historical Replay Transparency**: All UI components and API responses explicitly indicate `HISTORICAL REPLAY — NOT LIVE FORECAST`.
5. **Offline Independence**: Requires zero external network API calls to run.
