# GramDrishti — Phase 1 Data Compatibility Audit
## SIH PS 26074: Panchayat-Level Weather Downscaling for Agro-Advisories

---

## Audit Status: **BLOCKED — No Real Data Acquired**

This audit cannot be completed until real datasets are acquired and ingested.
All checks below are marked UNVERIFIED.

---

## Compatibility Checks

| # | Check                                                     | Status       | Notes                               |
|---|----------------------------------------------------------|-------------|--------------------------------------|
| 1 | Station coordinates fall within/near pilot region?       | UNVERIFIED  | No pilot region selected. No station data acquired. |
| 2 | Forecast coverage overlaps pilot region?                 | UNVERIFIED  | No forecast data acquired.           |
| 3 | DEM covers the pilot region?                             | UNVERIFIED  | No DEM data acquired.                |
| 4 | Land-cover layers cover pilot region?                    | UNVERIFIED  | No landcover data acquired.          |
| 5 | Water/coast layers overlap pilot region?                 | UNVERIFIED  | No water data acquired.              |
| 6 | CRS compatible across all datasets?                      | UNVERIFIED  | Expected: EPSG:4326 for all.         |
| 7 | Observation dates overlap forecast dates?                | UNVERIFIED  | No temporal data to compare.         |
| 8 | Forecast issue/valid times available?                    | UNVERIFIED  | No forecast data.                    |
| 9 | Station observations sufficient for future validation?   | UNVERIFIED  | Need minimum station density.        |
|10 | Major spatial gaps?                                      | UNVERIFIED  | Cannot assess without data.          |

---

## Dataset Readiness Classification

| Dataset      | Classification | Reason                                        |
|-------------|----------------|-----------------------------------------------|
| Boundaries  | MISSING        | No panchayat boundary data acquired            |
| Observations| MISSING        | No station observation data acquired           |
| Forecasts   | MISSING        | No forecast data acquired                      |
| DEM         | MISSING        | No DEM raster acquired                         |
| Landcover   | MISSING        | No LULC data acquired                          |
| Water/Coast | MISSING        | No water body data acquired                    |

Classification definitions:
- **READY**: Data acquired, validated, and compatible with other layers.
- **PARTIAL**: Data acquired but incomplete or has known issues.
- **MISSING**: Data not yet acquired.
- **UNVERIFIED**: Data present but compatibility not yet checked.

---

## Actions Required

1. Select pilot region based on data availability (see `pilot_region_selection.md`).
2. Acquire panchayat boundary data for the selected region.
3. Acquire weather station observation data for stations in/near the region.
4. Acquire forecast data covering the region.
5. Download DEM tile(s) covering the region.
6. Download LULC data covering the region.
7. Download water body / coastline data.
8. Re-run this audit after each dataset is acquired.

---

## Re-Running This Audit

After data is acquired and ingested, re-run validation:

```bash
python -m src.ingestion.validate_dataset --validate-all --json
```

Then update this document with actual results.
