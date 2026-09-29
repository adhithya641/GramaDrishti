# GramDrishti — Phase 1 Data Dictionary
## SIH PS 26074: Panchayat-Level Weather Downscaling for Agro-Advisories

---

## 1. Panchayat Boundaries

Administrative boundary polygons for panchayat-level governance areas.

| Field            | Type     | Unit   | Source    | Purpose                          | Missing Behaviour          |
|-----------------|----------|--------|-----------|----------------------------------|----------------------------|
| panchayat_name  | string   | -      | UNKNOWN   | Identifies panchayat             | Error: required            |
| panchayat_code  | string   | -      | UNKNOWN   | Unique ID for panchayat          | Warning: optional          |
| block_name      | string   | -      | UNKNOWN   | Parent block                     | Warning: optional          |
| district_name   | string   | -      | UNKNOWN   | Parent district                  | Error: required            |
| state_name      | string   | -      | UNKNOWN   | Parent state                     | Error: required            |
| geometry        | Polygon  | -      | UNKNOWN   | Spatial boundary                 | Error: required            |
| area_sq_km      | float    | km²    | Derived   | Area of panchayat                | Warning: optional          |

---

## 2. Weather Station Observations

Ground-level weather measurements from meteorological stations.

| Field              | Type      | Unit    | Source    | Purpose                       | Missing Behaviour          |
|-------------------|-----------|---------|-----------|-------------------------------|----------------------------|
| station_id        | string    | -       | UNKNOWN   | Unique station identifier     | Error: required            |
| timestamp         | datetime  | -       | UNKNOWN   | Time of observation           | Error: required            |
| latitude          | float     | degrees | UNKNOWN   | Station latitude (WGS84)      | Error: required            |
| longitude         | float     | degrees | UNKNOWN   | Station longitude (WGS84)     | Error: required            |
| temperature       | float     | °C      | UNKNOWN   | Air temperature               | QC: MISSING                |
| humidity          | float     | %       | UNKNOWN   | Relative humidity             | QC: MISSING                |
| rainfall          | float     | mm      | UNKNOWN   | Accumulated rainfall          | QC: MISSING                |
| pressure          | float     | hPa     | UNKNOWN   | Atmospheric pressure          | QC: MISSING                |
| wind_speed        | float     | km/h    | UNKNOWN   | Wind speed                    | QC: MISSING                |
| station_elevation | float     | m       | UNKNOWN   | Elevation of station          | Warning: optional          |

### QC Classification

| Code       | Meaning                                              |
|-----------|------------------------------------------------------|
| VALID      | Value present and passes all range/consistency checks |
| MISSING    | Value is null, NaN, or absent                        |
| SUSPICIOUS | Present but outside expected soft range               |
| INVALID    | Fails type check or exceeds hard physical limits      |

### Physical Range Limits

| Variable    | Soft Range         | Hard Range         |
|------------|--------------------|--------------------|
| temperature | -10°C to 52°C     | -60°C to 60°C     |
| humidity    | 5% to 100%        | 0% to 100%        |
| rainfall    | 0mm to 500mm      | 0mm to 1000mm     |
| pressure    | 940hPa to 1060hPa | 870hPa to 1085hPa |
| wind_speed  | 0 to 100 km/h     | 0 to 200 km/h     |

---

## 3. Weather Forecasts

Coarse-resolution NWP model output.

| Field               | Type      | Unit    | Source    | Purpose                        | Missing Behaviour  |
|--------------------|-----------|---------|-----------|--------------------------------|--------------------|
| forecast_issue_time | datetime  | -       | UNKNOWN   | When forecast was generated    | Error: required    |
| valid_time          | datetime  | -       | UNKNOWN   | What time forecast is valid for| Error: required    |
| lead_time           | float     | hours   | UNKNOWN   | valid_time - issue_time        | Error: required    |
| latitude            | float     | degrees | UNKNOWN   | Grid point latitude            | Error: required    |
| longitude           | float     | degrees | UNKNOWN   | Grid point longitude           | Error: required    |
| temperature         | float     | °C      | UNKNOWN   | Forecast temperature           | Warning: optional  |
| humidity            | float     | %       | UNKNOWN   | Forecast humidity              | Warning: optional  |
| rainfall            | float     | mm      | UNKNOWN   | Forecast rainfall              | Warning: optional  |
| wind_speed          | float     | km/h    | UNKNOWN   | Forecast wind speed            | Warning: optional  |
| pressure            | float     | hPa     | UNKNOWN   | Forecast pressure              | Warning: optional  |

> **IMPORTANT**: Reanalysis data must NOT be treated as historical forecasts.

---

## 4. Digital Elevation Model (DEM)

Gridded elevation data.

| Field      | Type   | Unit   | Source    | Purpose            | Missing Behaviour         |
|-----------|--------|--------|-----------|--------------------|--------------------------  |
| elevation | float  | m      | UNKNOWN   | Surface elevation  | nodata value in raster     |

- **Resolution**: UNKNOWN (expected 30m or 90m)
- **CRS**: Expected EPSG:4326
- Slope, aspect, TRI are NOT computed in Phase 1.

---

## 5. Land Use / Land Cover (LULC)

Classification raster or vector data.

| Field            | Type    | Unit   | Source    | Purpose                    | Missing Behaviour      |
|-----------------|---------|--------|-----------|----------------------------|------------------------|
| landcover_class | integer | -      | UNKNOWN   | Land use classification    | nodata in raster       |
| ndvi            | float   | -      | UNKNOWN   | Vegetation index           | Warning: optional      |
| crop_type       | string  | -      | UNKNOWN   | Specific crop              | Warning: optional      |

- ML features are NOT computed in Phase 1.

---

## 6. Water Bodies and Coastline

Vector polygons/lines for water features.

| Field           | Type    | Unit   | Source    | Purpose                  | Missing Behaviour      |
|----------------|---------|--------|-----------|--------------------------|------------------------|
| geometry       | Polygon | -      | UNKNOWN   | Water body shape         | Error: required        |
| water_body_name| string  | -      | UNKNOWN   | Name of water body       | Warning: optional      |
| water_body_type| string  | -      | UNKNOWN   | River/lake/reservoir/... | Warning: optional      |
| area_sq_km     | float   | km²    | UNKNOWN   | Area of water body       | Warning: optional      |
| is_coastal     | boolean | -      | UNKNOWN   | Coastal proximity flag   | Warning: optional      |

---

## Data Provenance Labels

Every dataset must carry one of these labels:

| Label        | Meaning                                           |
|-------------|---------------------------------------------------|
| REAL         | Official observed / operational data               |
| SYNTHETIC    | Generated for testing purposes                    |
| PLACEHOLDER  | Correct schema, no real values                    |
| STAND-IN     | Proxy data from an alternative source             |
| UNVERIFIED   | Source claimed but not independently verified      |
| UNAVAILABLE  | Data has not been acquired                        |
