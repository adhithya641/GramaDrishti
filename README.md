# GramDrishti — Terrain-Aware Panchayat Weather Downscaling & Agro-Advisory System
## SIH PS 26074 Demonstration Application

GramDrishti is a validation-driven correction layer over coarse weather forecasts for Gram Panchayat-level agricultural advisories.

---

## SIH Demo

### Run Demo Application

```bash
python scripts/run_demo.py
```

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000)

### Operating Modes

1. **LIVE MODE (Default)**: Real-time Coimbatore weather ingestion from Open-Meteo API (`https://api.open-meteo.com/v1/forecast`), public and open access (no API key required). Features live weather cards, IST timestamps (`Asia/Kolkata`), 24–48 hour hourly forecast timeline, live data provenance, and 5-minute auto-refresh.
2. **HISTORICAL REPLAY MODE**: Archived validated Coimbatore test period (May 01 – June 30, 2024). Evaluates GramDrishti ML downscaling models, conformal uncertainty intervals (CQR), block vs panchayat downscaling, and evidence-gated crop advisories across 180 Gram Panchayats.

### Pilot Region Scope & Coverage
* **Gram Panchayats**: 180 Gram Panchayats
* **Administrative Blocks**: 12 Blocks
* **Downscaled Spatial Grid**: 10,530 one-kilometre metric cells (EPSG:32643)
* **Observation Stations**: 8 ground weather stations

---

## Scientific Validation Metrics

### Temperature Correction
* **Coarse Physical Baseline B0 MAE**: `2.3165°C`
* **Forecast + Time Model A MAE**: `1.0823°C` (53.3% error reduction)
* **Full GIS Model B MAE**: `1.2225°C`
* *Finding*: Terrain/GIS features did **not** improve temperature accuracy over Model A in this pilot.

### Humidity Correction
* **Coarse Physical Baseline B0 MAE**: `25.5342%`
* **Forecast + Time Model A MAE**: `20.0937%`
* **Full GIS Model B MAE**: `19.4556%`

### Uncertainty & Reliability
* **Temperature CQR Test Coverage**: `87.70%` (Interval Width `4.73°C`, `HIGH` confidence)
* **Humidity CQR Test Coverage**: `20.15%` (Interval Width `27.61%`, flagged `LOW` reliability due to monsoon onset distribution shift)
* **Rainfall Data Scarcity**: Rainfall ≥10 mm and ≥25 mm thresholds are explicitly classified `NOT_EVALUABLE` due to historical event scarcity. Zero probabilities are fabricated.

---

## Disclaimers & Pilot Scope
* GramDrishti is a validation-driven correction layer over coarse weather forecasts. It does not replace operational forecasts or establish panchayat-scale ground truth.
* Forecast source in this pilot is a stand-in historical forecast dataset derived from Open-Meteo archives.
