# GramDrishti — Phase 8 Application Layer Documentation

## Executive Overview
**GramDrishti** is an AI-assisted hyperlocal weather intelligence platform developed for **Smart India Hackathon (SIH) PS 26074**. 

> **Crucial Guarantee**: Phase 8 is strictly an **application and presentation layer** and does not retrain or modify the underlying forecasting models, conformal quantile bounds, or previous-phase data artifacts.

---

## 1. Application Architecture

Phase 8 is structured as a decoupled, modular Streamlit + Python application that consumes existing artifacts as read-only inputs:

```text
app/
├── __init__.py                # Package initialization & versioning
├── main.py                    # Multi-page interactive Streamlit dashboard
├── data_loader.py             # Read-only ingestion with schema validation
├── services.py                # High-level business logic & Plotly chart generators
├── schemas.py                 # Strict data schemas & physical validation rules
├── formatting.py              # Metric formatters, HTML badges, and ASCII prob bars
├── components/                # Modular UI components
│   ├── __init__.py
│   ├── header.py              # District branding & system freshness banner
│   ├── forecast_cards.py      # Temperature & humidity cards with UQ widths
│   ├── uncertainty.py         # Visual CQR bands (P10 — P50 — P90)
│   ├── rainfall.py            # Calibrated probabilities & evaluability guards
│   ├── advisory.py            # Crop advisory boundary placeholder (Phase 7)
│   ├── reliability.py         # Reliability & reason code reporting (Phase 7)
│   └── map_view.py            # 180 Panchayat choropleth & 8 IMD stations map
└── assets/                    # Static branding assets
```

---

## 2. Installation & Environment Setup

Phase 8 introduces a standalone requirements specification in `requirements_phase8.txt` without disturbing core project dependencies:

```bash
pip install -r requirements_phase8.txt
```

### Dependencies
* `streamlit >= 1.35.0`
* `pandas >= 2.0.0`
* `numpy >= 1.24.0`
* `plotly >= 5.18.0`
* `pyyaml >= 6.0.0`

---

## 3. Startup Command

To launch the GramDrishti application locally from the repository root:

```bash
streamlit run app/main.py
```

The application starts an interactive local web server (default at `http://localhost:8501`).

---

## 4. Consumed Data Sources (Read-Only)

Phase 8 ingests the following pre-computed artifacts from Phases 1–6:

1. **Panchayat Rainfall Predictions (`data/processed/predictions/panchayat_rainfall_predictions.csv`)**:
   * 32,940 records covering all 180 Gram Panchayats across lead times +24h, +48h, +72h.
   * Provides calibrated $P(\text{Rain} \ge 1\text{mm})$, $P_{10}$ and $P_{90}$ spatial spread, and aggregation statuses (`OK` vs `SUBGRID_RANGE_UNRESOLVED`).
2. **Station Weather Predictions (`data/processed/predictions/weather_predictions.csv`)**:
   * LightGBM residual predictions and NWP baseline ladder ($B_0, B_1, B_2, B_3$) for 8 IMD meteorological stations.
3. **Conformal Uncertainty Predictions (`data/processed/predictions/uncertainty_predictions.csv`)**:
   * 80% coverage Conformalized Quantile Regression bounds ($P_{10}, P_{50}, P_{90}$) for temperature and humidity.
4. **Geospatial Boundaries & Metadata**:
   * `data/processed/boundaries/coimbatore_panchayats_processed.geojson` (180 Panchayat polygons)
   * `data/processed/geospatial/geospatial_features_master.csv` (10,530 1-km grid cell features)
   * `data/processed/predictions/station_rainfall_predictions.csv` (Station coordinates & elevations)

---

## 5. Supported Features & Pages

The application provides a comprehensive suite of views accessible via the sidebar navigation:

1. 📊 **Panchayat Dashboard**:
   * Dynamic dropdown of all 180 Panchayats (searchable by Name or Block).
   * Key Panchayat metrics (Code, Block, Mean Elevation, 1-km Grid Cell count).
   * Temperature and Humidity forecast cards with uncertainty ranges.
   * Hyperlocal rainfall probability cards.
   * Conformal uncertainty preview.
2. 🌡️ **Temperature & Humidity**:
   * Detailed temperature and relative humidity forecasts.
   * Model comparison ladder ($B_0$ Raw NWP, $B_1$ Lapse Rate, $B_2$ Geospatial, $B_3$ Quantile Mapping, ML Residual vs Observed).
   * Interactive whisker / gauge visualizations for $P_{10} \text{ — } P_{50} \text{ — } P_{90}$.
3. 🌧️ **Hyperlocal Rainfall Intelligence**:
   * Rain $\ge 1.0\text{ mm}$ calibrated probability with horizontal progress bar.
   * Rain $\ge 10.0\text{ mm}$ marked as `Data-Limited` (insufficient training events).
   * Rain $\ge 25.0\text{ mm}$ marked as `Not Evaluable` (unobserved in regional historical record).
   * Multi-lead time rainfall evolution chart (+24h, +48h, +72h).
4. 🗺️ **District Spatial Map**:
   * Interactive map of Coimbatore District with all 180 Panchayats and 8 IMD Observation Stations.
   * Visual indicators for active Panchayat selection and spatial rainfall intensity.
5. 📈 **Model Performance & Audits**:
   * Station-level MAE / RMSE performance tables.
   * Top predictive LightGBM feature importance rankings.
   * Phase 5 Conformal coverage validation report.
   * Phase 6 Rainfall baseline Brier score comparison ($R_0, R_1, R_2$).
6. 🛡️ **Forecast Reliability**:
   * Transparent reliability classification and reason codes.
   * Graceful handling when Phase 7 artifacts are not present.
7. 🌾 **Crop Advisory**:
   * Agricultural advisory integration boundary.
   * Clearly marked placeholder when Phase 7 is unavailable without inventing synthetic recommendations.
8. ℹ️ **About & Scientific Policy**:
   * Complete SIH PS 26074 background, pilot constraints, and scientific integrity principles.

---

## 6. Standalone Phase 7 Handling (Missing Artifacts)

Phase 7 (Reliability Engine & Crop Advisory Synthesis) is developed on a separate pipeline:
* **Missing Reliability File (`panchayat_reliability.csv`)**: The application displays:
  > `Reliability information unavailable. Phase 7 reliability artifacts are not present in this deployment.`
  and provides the Phase 5/6 statistical validation summary as factual context.
* **Missing Crop Advisories**: The application displays:
  > `Advisory engine data is not available in this deployment.`
  No synthetic or unvalidated crop advisories are generated.

---

## 7. Scientific Data Validation & Safety Rules

Before any value is rendered on screen, it is checked against strict scientific bounds:
1. **Physical Temperature Limits**: $-10^\circ\text{C} \le T \le 60^\circ\text{C}$.
2. **Relative Humidity Range**: $0\% \le \text{RH} \le 100\%$.
3. **Probability Range**: $0.0 \le P \le 1.0$.
4. **Quantile Ordering**: Monotonic condition $P_{10} \le P_{50} \le P_{90}$ is strictly verified.
5. **No Fabricated Zeros**: Unobserved or data-limited thresholds ($\ge 10\text{mm}, \ge 25\text{mm}$) remain strictly `None` / `NOT_EVALUABLE`.
6. **Withholding Policy**: Any record failing validation triggers `Data validation error — value withheld`.

---

## 8. Limitations & Domain Scope

1. **Pilot Scope**: Localized exclusively to **Coimbatore District, Tamil Nadu**. No nationwide deployment claim is made.
2. **Humidity UQ Limitation**: Test set coverage is limited (20.15%) due to a strong summer seasonal distribution shift (dry season training vs wet pre-monsoon test period).
3. **Extreme Precipitation**: The regional dataset contains 0 historical records of $\ge 25\text{ mm}$ daily precipitation; risk estimates for extreme deluge events are un-evaluable.
4. **Boundary Edge Cases**: Two Panchayats (`GP_33_12_0114`, `GP_33_12_0165`) have status `SUBGRID_RANGE_UNRESOLVED` due to single-cell border overlap.
