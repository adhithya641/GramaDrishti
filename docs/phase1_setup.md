# GramDrishti — Phase 1 Setup & Reproducibility Guide
## SIH PS 26074: Panchayat-Level Weather Downscaling for Agro-Advisories

---

## 1. Environment Setup

* **Python Version:** Python 3.10 / 3.11 / 3.12
* **Operating System:** Windows / Linux / macOS

### Dependencies Installation

```bash
cd D:\GramDrishti
python -m pip install -r requirements.txt
python -m pip install geopandas rasterio shapely requests pillow tifffile
```

---

## 2. Dataset Acquisition Execution

To acquire and process all six Phase 1 datasets for the selected pilot region (**Coimbatore District, Tamil Nadu**):

```bash
python scripts/acquire_coimbatore_data.py
```

This populates `data/raw/` with:
- `data/raw/boundaries/coimbatore_panchayats.geojson` (180 Gram Panchayats)
- `data/raw/observations/coimbatore_station_observations.csv` (34,944 hourly station records)
- `data/raw/forecasts/coimbatore_historical_forecasts.csv` (6,552 historical forecast records, labeled STAND-IN)
- `data/raw/dem/coimbatore_dem_30m.tif` (300x400 GeoTIFF elevation raster)
- `data/raw/landcover/coimbatore_landcover_10m.tif` (300x400 GeoTIFF LULC raster)
- `data/raw/water/coimbatore_water_bodies.geojson` (7 hydrography river/reservoir vector features)

---

## 3. Data Validation & Processing Commands

### Check Configuration

```bash
python -m src.ingestion.validate_dataset --validate-config
```

### Validate and Ingest All Datasets

```bash
python -m src.ingestion.validate_dataset --validate-all
```

This runs QC & validation across all raw layers and produces processed outputs under `data/processed/` and metadata reports under `data/metadata/`.

---

## 4. Running Pytest Suite

```bash
python -m pytest tests/ -v
```

Expected result: **48/48 unit tests passing**.

---

## 5. Dataset Source URLs & Credentials

| Dataset | Primary Public Source URL | API Credentials Required? | Status |
| :--- | :--- | :--- | :--- |
| **Boundaries** | `https://github.com/datameet/maps` | None | **REAL** |
| **Observations** | `https://archive-api.open-meteo.com/v1/archive` | None | **REAL** |
| **Forecasts** | `https://archive-api.open-meteo.com` | None | **STAND-IN** |
| **DEM** | `https://copernicus-dem-30m.s3.amazonaws.com` | None | **REAL** |
| **Land Cover** | `https://esa-worldcover.org` | None | **REAL** |
| **Water / Hydro** | `https://www.naturalearthdata.com` | None | **REAL** |

---

## 6. Access Limitations & Notes

* **Forecast Stand-in Notice:** Sourced from Open-Meteo operational model run archives (ECMWF IFS / GFS). Preserves `forecast_issue_time`, `valid_time`, and `lead_time`. Labeled strictly as `data_status: STAND-IN`.
* **C-DLL App Control Compatibility:** Ingestion ingestors feature fallback mechanisms to `json` / `tifffile` to ensure execution without GDAL DLL block issues on Windows systems.
