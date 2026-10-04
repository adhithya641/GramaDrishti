# GramDrishti — Phase 10B UI & Live Dashboard Upgrade

## Dashboard Design & Architecture

Phase 10B introduces a live-first dashboard experience built with vanilla HTML5, CSS3, JavaScript (ES6+), and Leaflet.js.

---

## Key Interface Components

### 1. Header & Mode Switcher
- **Header**: Displays `GRAMDRISHTI | Panchayat Weather Intelligence • Coimbatore, TN`.
- **Mode Toggle**: Prominently features a dual-state switch: `● LIVE` (default) vs `📜 HISTORICAL REPLAY`.
- **Status Pill**: Dynamic status badge indicating API connectivity (`Open-Meteo: LIVE (FRESH)` vs `Open-Meteo: CACHED`).

### 2. Live Weather Mode View
- **Current Weather Cards**:
  - Temperature (°C) & Apparent Temperature (°C)
  - Relative Humidity (%)
  - Precipitation (mm)
  - Wind Speed (km/h & m/s) & Direction (°)
  - Surface Pressure (hPa) & Cloud Cover (%)
  - Weather Condition Emoji & Description (WMO Standard)
- **IST Timestamp & Provenance Bar**: Converts all timestamps to `Asia/Kolkata` (IST) format (e.g. `04 Oct 2026, 21:07:32 IST`).
- **Hourly Forecast Timeline**: Scrollable 24–48 hour forecast timeline cards powered dynamically by `/api/live/forecast`.
- **Coimbatore Map Context**: Interactive Leaflet map displaying 180 Gram Panchayat boundaries with a live regional weather overlay banner.
- **Data Source Panel**: Invariant provider attribution (Open-Meteo CC BY 4.0), coordinates, age in seconds, and status.
- **Auto-Refresh**: 5-minute automatic refresh timer with countdown and manual `↻ Refresh Now` action.

### 3. Historical Replay Mode View
- **Historical Banner**: `⚠️ HISTORICAL REPLAY MODE — Archived Pilot Test Period (May 01 – Jun 30, 2024)`.
- **Historical Control Bar**: Select Replay Date (2024 dates), Lead Time (24h/48h/72h), and Variable buttons (Temperature, Humidity, Rain thresholds).
- **Model Output Visualizations**: Conformal uncertainty quantification (P10/P50/P90), block vs panchayat spatial downscaling, and evidence-gated crop advisories.

---

## API Endpoints

- `GET /api/live/weather`: Current Coimbatore weather with explicit provenance and validation payload.
- `GET /api/live/forecast`: 24-48 hour hourly forecast timeline.
- `GET /api/live/status`: System connectivity and cache health check.
- `GET /api/live/source`: Provider metadata and attribution.
- `GET /api/health`: System health and mode label.
- `GET /api/v1/metadata`: System metadata reporting `"default_mode": "LIVE"`.
