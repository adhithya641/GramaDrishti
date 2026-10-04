# GramDrishti — Phase 8: Implementation Plan
## Dashboard + API Integration + Offline Demo Layer

---

## Executive Summary

Phase 8 implements a fully functional prototype dashboard and REST API server for GramDrishti (SIH PS 26074). The primary goal is to provide an intuitive, transparent interface connecting raw dataset artifacts to downscaled panchayat predictions, uncertainty intervals, evidence-based reliability statuses, fallback sources, and evidence-gated crop advisories without exposing internal Python code to jurors or end-users.

All Phase 1–7 scientific results, dataset schemas, canonical metrics, and documented limitations remain strictly preserved.

---

## 1. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Phase 8 FastAPI Service Layer                        │
│                     (src/dashboard/service.py)                         │
└────────────────────────────────────────────────────────────────────────┘
       ▲                                ▲                               ▲
       │                                │                               │
┌───────────────┐              ┌─────────────────┐             ┌─────────────────┐
│ Prediction    │              │ GeoJSON         │             │ Phase 7         │
│ CSV Artifacts │              │ Boundaries      │             │ Reliability API │
└───────────────┘              └─────────────────┘             └─────────────────┘
       │                                │                               │
       └────────────────────────────────┼───────────────────────────────┘
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 GramDrishti Interactive Dashboard                      │
│                  (src/dashboard/static/index.html)                     │
│                                                                        │
│ ┌──────────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│ │ Interactive Map      │  │ Panchayat Detail │  │ Block vs Panchayat │ │
│ │ (180 Panchayats)     │  │ & UQ Gauges      │  │ Spatial Variation  │ │
│ └──────────────────────┘  └──────────────────┘  └────────────────────┘ │
│ ┌──────────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│ │ Replay Selector      │  │ Gated Advisory   │  │ Health Status      │ │
│ │ (May 01 – Jun 30)    │  │ Panel            │  │ Matrix             │ │
│ └──────────────────────┘  └──────────────────┘  └────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. API Specifications

| Endpoint | Method | Description | Response Payload |
|---|---|---|---|
| `/` | `GET` | Serves main interactive dashboard UI | HTML5 Single-Page App |
| `/api/v1/system-status` | `GET` | Returns runtime health status matrix | JSON Object |
| `/api/v1/metadata` | `GET` | Project metadata & dataset validation timestamps | JSON Object |
| `/api/v1/timestamps` | `GET` | List of distinct historical forecast timestamps | JSON Array |
| `/api/v1/panchayats` | `GET` | List of 180 Gram Panchayats with block metadata | JSON Array |
| `/api/v1/geojson` | `GET` | GeoJSON FeatureCollection with predictions | GeoJSON |
| `/panchayat/{id}/forecast` | `GET` | Panchayat prediction detail, UQ, and fallback | JSON Object |
| `/panchayat/{id}/reliability` | `GET` | Phase 7 evidence-based reliability report | JSON Object |
| `/panchayat/{id}/advisory` | `GET` | Gated crop advisories | JSON Object |
| `/api/v1/block-comparison` | `GET` | Coarse district forecast vs downscaled panchayats | JSON Object |

---

## 3. UI Dashboard Features

1. **Header & Badges**: Displays project branding, pilot scope (Coimbatore, 180 Panchayats), data mode (`OFFLINE REPLAY`), and operational status.
2. **Replay & Filter Toolbar**: Date selector (61 test dates), lead time selector (24, 48, 72h), and variable buttons (Temperature, Humidity, Rain ≥1mm, Rain ≥10mm, Rain ≥25mm).
3. **Mandatory Banner**: Prominently labels replay mode: `HISTORICAL REPLAY — NOT LIVE FORECAST`.
4. **Interactive Leaflet Map**: Displays 180 Gram Panchayat polygon boundaries colored by downscaled value or reliability. Handles `NOT_EVALUABLE` rainfall thresholds with explicit notices.
5. **Panchayat Detail Panel**: Location, 1 km cell count, subgrid status (`OK` vs `SUBGRID_RANGE_UNRESOLVED`), CQR uncertainty intervals (P10 ── P50 ── P90), interval width, and active fallback source badge.
6. **Block vs Panchayat Comparison**: Demonstrates spatial variation within coarse forecast domain (e.g. 32.4°C coarse vs 30.8°C – 34.0°C panchayat range) labeled `Historical replay / model output`.
7. **Uncertainty & Reliability Panel**: Displays CQR bounds with explicit undercoverage warning for Humidity (`LOW RELIABILITY — temporal distribution shift detected`).
8. **Agro-Advisory Panel**: Gated crop advice (`ACTIONABLE`, `CAUTIONARY`, `BLOCKED`).
9. **System Health Matrix**: Real-time checks for Data, Model, and Output layers.
10. **Scientific Disclaimers**: Disclaims operational forecast replacement and specifies historical stand-in dataset origin.

---

## 4. Offline Demo Capabilities

* Operates 100% offline without internet connection after startup.
* Reads directly from local CSV, JSON, and GeoJSON files in `data/processed/`.
* Includes graceful fallbacks for missing data records.
