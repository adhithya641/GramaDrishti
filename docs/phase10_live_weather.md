# GramDrishti — Phase 10B Live Weather Ingestion & Data Provenance

## Overview

Phase 10B transitions GramDrishti to a live-first demonstration interface for real-time weather monitoring in Coimbatore, Tamil Nadu, while preserving the validated historical ML downscaling model for 2024 experiment evaluation.

---

## Data Source & API Integration

- **Provider**: Open-Meteo API (`https://api.open-meteo.com/v1/forecast`)
- **Access**: Public / Open Source (CC BY 4.0) — **No API key required**
- **Location**: Coimbatore, Tamil Nadu (`11.0168° N, 76.9558° E`, Elevation 431 m)
- **Timezone**: `Asia/Kolkata` (IST)
- **Variables Ingested**:
  - Current Temperature (°C) & Apparent Temperature (°C)
  - Relative Humidity (%)
  - Precipitation Intensity (mm)
  - Wind Speed (km/h & m/s) and Wind Direction (°)
  - Surface Pressure (hPa) and Cloud Cover (%)
  - WMO Weather Condition Codes
  - 24–48 Hour Hourly Forecast Timeline

---

## Mode Separation & Provenance Control

### 1. LIVE MODE (Default)
- Direct ingestion of current Open-Meteo observations and 48-hour forecasts for Coimbatore.
- All user-facing timestamps are displayed in **IST (`Asia/Kolkata`)**.
- Explicit provenance object returned in `/api/live/weather`:
  ```json
  {
    "mode": "LIVE",
    "source": "Open-Meteo",
    "latitude": 11.0168,
    "longitude": 76.9558,
    "observed_at": "2026-10-04T20:45",
    "fetched_at": "2026-10-04T15:30:00+00:00",
    "data_age_seconds": 12.5,
    "freshness": "LIVE_FRESH"
  }
  ```

### 2. HISTORICAL REPLAY MODE
- Archived pilot test period (May 01 – Jun 30, 2024).
- Evaluates the validated GramDrishti ML downscaling model, conformal uncertainty quantification (CQR), block vs panchayat downscaling, and evidence-gated crop advisories across 180 Gram Panchayats.

---

## Failover & Fallback Chain

1. **LIVE API (`LIVE_FRESH` / `LIVE_AGING`)**: Direct network call to Open-Meteo.
2. **LOCAL CACHE (`LIVE_STALE`)**: Uses `data/cache/live_weather.json` if network fails. Prominently displays `LIVE DATA — CACHED`.
3. **HISTORICAL REPLAY (`EXPIRED`)**: If API is unreachable and cache is unavailable/expired, automatically degrades to Historical Replay mode with explicit UI alert notification.

---

## Scientific Limitation & Integrity

- **Live Data Scope**: Live weather displays direct Open-Meteo regional observations for Coimbatore.
- **Model Validation Boundary**: The GramDrishti downscaling model and conformal uncertainty bounds are validated against historical ground station data (Jan–Jun 2024). Live regional observations are explicitly labeled as `LIVE REGIONAL WEATHER` throughout the application interface.
