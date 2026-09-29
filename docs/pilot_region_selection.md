# Pilot Region Selection Report — GramDrishti (Phase 1)

**Project:** GramDrishti — Panchayat-Level Weather Downscaling for Agro-Advisories  
**Problem Statement:** SIH PS 26074  
**Date:** September 2026  
**Selected Pilot Region:** **Coimbatore District, Tamil Nadu, India**

---

## 1. Candidate Regions Evaluated

Four candidate districts in Tamil Nadu were evaluated based on the availability and quality of data across all six Phase 1 data layers (Panchayat Boundaries, Weather Observations, Historical Forecasts, DEM, Land Cover, Water/Coastline):

| Evaluation Criterion | Nilgiris District | Coimbatore District | Cuddalore District | Madurai District |
| :--- | :--- | :--- | :--- | :--- |
| **Panchayat Boundary Availability** | Moderate (Town Panchayats dominant) | **High** (Gram Panchayats across 12 blocks) | High (Coastal Gram Panchayats) | High |
| **Weather Station Density** | Moderate (Highland stations) | **High** (IMD Peelamedu, TNAU, AWS network) | Moderate (Coastal AWS) | Moderate |
| **Historical Forecast Archives** | High (Gridded GFS/IFS) | **High** (Gridded GFS/IFS) | High | High |
| **DEM Elevation Gradient** | Very High (800m - 2637m) | **High** (180m - 2500m Western Ghats slope) | Low (Coastal plain 0-50m) | Moderate (100m - 1400m) |
| **Land Cover Diversity** | Forest / Plantation dominant | **High** (Cropland, Irrigated, Scrub, Forest, Built-up) | Cropland / Coastal | Cropland / Scrub |
| **Water / Hydrology Coverage** | High (Reservoirs) | **High** (Bhavani, Noyyal, Aliyar, Reservoirs) | High (Coastal / Rivers) | Moderate (Vaigai system) |
| **Downscaling Suitability** | High terrain complexity | **Ideal** (Terrain contrast + intense agriculture) | Coastal dynamics | Moderate |

---

## 2. Selected Pilot Region Details

### **Selected Pilot:** **Coimbatore District, Tamil Nadu**

* **State:** Tamil Nadu
* **District:** Coimbatore
* **Administrative Hierarchy:** State (Tamil Nadu) → District (Coimbatore) → Blocks (12 Blocks: Anaimalai, Annur, Karamadai, Kinathukadavu, Madukkarai, Perur, Pollachi North, Pollachi South, Sulur, Thondamuthur, SS Kulam, Valparai) → Gram Panchayats (228+ Gram Panchayats)
* **Geographic Extent (Bounding Box):**
  * **Latitude Range:** `10.2000° N` to `11.4000° N`
  * **Longitude Range:** `76.6000° E` to `77.3000° E`
  * **Center:** ~`10.99° N, 76.96° E`
* **Coordinate Reference System (CRS):** `EPSG:4326` (WGS 84)

---

## 3. Rationale for Selection

1. **Topographic Heterogeneity:**
   Coimbatore district spans from flat eastern agricultural plains (~180m elevation) to the steep western slopes of the Western Ghats (~2,500m elevation at Valparai/Anamalai). This elevation gradient is **essential** for evaluating terrain-aware temperature and rainfall downscaling models in Phase 2.

2. **Agro-Meteorological Importance:**
   Coimbatore is a major agricultural hub (cotton, sugarcane, maize, millets, coconut, tea, horticultural crops) and houses the Tamil Nadu Agricultural University (TNAU) Agro-Climate Research Centre.

3. **Weather Station Network:**
   Contains primary IMD weather stations (Peelamedu / Coimbatore Airport `IND00043321`), TNAU Met Observatory, and regional AWS networks (Pollachi, Annur, Mettupalayam, Valparai), providing robust ground truth.

4. **Complete Multi-Layer Data Feasibility:**
   All six required layers (vector boundaries, ground stations, historical forecasts, DEM, land cover, water bodies) can be acquired from public authoritative sources for this exact bounding box.

---

## 4. Layer-by-Layer Data Source Assessment

| Layer | Source / Product | Coverage Status | Quality / Resolution |
| :--- | :--- | :--- | :--- |
| **1. Panchayat Boundaries** | LGD / Open Data India / OSM Admin Boundaries | Complete for Coimbatore District | Vector (Polygon) |
| **2. Weather Observations** | NOAA GHCN-D / GSOD & IMD Station Archives | 10+ Stations in/around pilot box | Daily / Hourly observations |
| **3. Coarse Forecasts** | Open-Meteo Historical Forecast Archive (GFS/ECMWF) | Complete 0.25° / 0.1° grid coverage | Hourly issue/valid time preservation (STAND-IN) |
| **4. DEM / Elevation** | Copernicus DEM / SRTM 30m | 100% coverage (10.2°-11.4°N, 76.6°-77.3°E) | 1-arcsec (~30m) raster |
| **5. Land Cover** | ESA WorldCover 10m / Copernicus LULC | 100% coverage | 10m / 100m raster classes |
| **6. Water / Hydrography** | Natural Earth / OpenStreetMap Hydrography | Complete (Bhavani, Noyyal, Reservoirs) | Vector Line & Polygon |

---

## 5. Limitations & Data Gaps

* **Forecast Stand-in Notice:** Operational IMD NWP forecast API feeds require government credentials. Operational model forecast archives from Open-Meteo (preserving `forecast_issue_time`, `valid_time`, `lead_time`) are used as a documented **STAND-IN**.
* **Panchayat Resolution:** Certain remote hill Gram Panchayats in Valparai block are grouped under tea estate divisions; standard admin 7/8 polygons cover all registered Gram Panchayats.

---

## 6. Pilot Region Selection Status

**Status:** **SELECTED** — Coimbatore District, Tamil Nadu.
