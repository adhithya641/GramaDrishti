# GramDrishti Phase 10A — Live Weather Data Source Documentation

## Provider

**Open-Meteo** — [https://open-meteo.com](https://open-meteo.com)

Open-Meteo is an open-source weather API that aggregates data from multiple national meteorological services (DWD, ECMWF, GFS, MeteoFrance, UKMO, and others) and provides free access for non-commercial use.

---

## API Endpoint

```
GET https://api.open-meteo.com/v1/forecast
```

**No API key required** for non-commercial / prototype use.

### Request for Coimbatore

```
https://api.open-meteo.com/v1/forecast?
  latitude=11.0168&
  longitude=76.9558&
  current=temperature_2m,relative_humidity_2m,apparent_temperature,
          precipitation,weather_code,surface_pressure,
          wind_speed_10m,wind_direction_10m,cloud_cover&
  hourly=temperature_2m,relative_humidity_2m,
         precipitation_probability,precipitation,weather_code&
  forecast_days=2&
  timezone=Asia/Kolkata
```

---

## Variables

### Current (real-time observation)

| Variable | Unit | Description |
|---|---|---|
| `temperature_2m` | °C | 2m air temperature |
| `relative_humidity_2m` | % | Relative humidity at 2m |
| `apparent_temperature` | °C | Feels-like temperature |
| `precipitation` | mm | Current precipitation |
| `weather_code` | WMO code | Weather condition code |
| `surface_pressure` | hPa | Surface air pressure |
| `wind_speed_10m` | km/h | Wind speed at 10m (converted to m/s internally) |
| `wind_direction_10m` | ° | Wind direction at 10m |
| `cloud_cover` | % | Total cloud cover |

### Hourly Forecast (next 48h)

| Variable | Unit | Description |
|---|---|---|
| `temperature_2m` | °C | Hourly temperature |
| `relative_humidity_2m` | % | Hourly humidity |
| `precipitation_probability` | % | Probability of precipitation |
| `precipitation` | mm | Precipitation amount |
| `weather_code` | WMO code | Hourly weather code |

---

## Units (Internal GramDrishti Schema)

| Field | Source Unit | Internal Unit |
|---|---|---|
| `temperature_c` | °C | °C |
| `apparent_temperature_c` | °C | °C |
| `relative_humidity_pct` | % | % |
| `precipitation_mm` | mm | mm |
| `surface_pressure_hpa` | hPa | hPa |
| `wind_speed_ms` | km/h → converted | m/s |
| `wind_speed_kmh` | km/h | km/h (raw) |
| `wind_direction_deg` | ° | ° |
| `cloud_cover_pct` | % | % |

---

## Update Frequency

- **Current weather**: Updated every 15 minutes (900-second interval)
- **Hourly forecast**: Updated once per model run cycle (~1–4 hours)
- **Forecast horizon**: Up to 16 days (this integration uses 2 days / 48h)

---

## Geographic Resolution

- Open-Meteo blends multiple models with different native resolutions
- For Coimbatore: primarily DWD ICON-D2 (2 km) + ECMWF IFS (9 km)
- Queried at point: Coimbatore centroid (11.0168°N, 76.9558°E)
- Elevation returned: ~431m (Coimbatore plateau)

---

## Limitations

1. **Regional observation only** — The Open-Meteo response represents the Coimbatore district centroid, NOT individual panchayat-level observations.
2. **Not validated against GramDrishti training data** — The GramDrishti Phase 4–7 models were trained and validated on a historical forecast-observation dataset. Live Open-Meteo data was NOT part of that validation.
3. **Not a downscaled output** — Live data passes directly from the API. The GramDrishti 1km downscaling model is NOT applied to live inputs in Phase 10A (compatibility of live inputs with the trained model requires further validation).
4. **No API key for prototype** — Suitable for SIH demonstration. For high-volume production, a paid plan is required.

---

## Attribution Requirements

> "Weather data by [Open-Meteo.com](https://open-meteo.com) — CC BY 4.0"

Attribution is displayed in the Data Sources panel of the dashboard.

---

## Fallback Behavior

```
Live API call (Open-Meteo)
          │
      Success?
     ┌─────┴──────┐
    YES           NO
     │             │
  LIVE DATA    Load disk cache
  (status: live)     │
                Cache exists?
               ┌────┴────┐
              YES        NO
               │          │
           LIVE DATA   HISTORICAL REPLAY
           — CACHED    (existing Phase 1–9
           (status:    validated artifacts)
            cached)
```

Status is always exposed in API responses as:
- `"live"` → LIVE DATA
- `"cached"` → LIVE DATA — CACHED
- `"historical_fallback"` → HISTORICAL REPLAY

The UI always shows the correct mode label. Stale/cached data is NEVER labeled as live.

---

## API vs Model Distinction (Critical)

| Layer | Source | Label |
|---|---|---|
| Live regional weather | Open-Meteo | `LIVE REGIONAL WEATHER` |
| GramDrishti model output | Phase 4–7 historical validation | `GRAMDRISHTI MODEL — Validation: Historical Coimbatore test set` |

These two are **never merged or conflated** in the UI or API responses.
