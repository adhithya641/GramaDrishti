# Phase 3 Weather Matchup & Baseline Data Dictionary
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

| Field Name | Data Type | Unit | Meaning | Calculation / Definition | Source Dataset | Missing-Value Handling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `station_id` | String | None | Ground weather station identifier | Station key (`STN_CBE_01` ... `STN_CBE_08`) | Phase 1 Observations | Primary key |
| `station_group` | String | None | Station group key for LOSO | Station grouping key (`GROUP_STN_CBE_01`) | Matchup Engine | Non-null |
| `observation_time` | Datetime | YYYY-MM-DD HH:MM | Timestamp of ground observation | Full datetime of station observation | Phase 1 Observations | Primary key |
| `forecast_issue_time` | Datetime | YYYY-MM-DD HH:MM | Forecast model generation timestamp | Model issue time (00:00 UTC) | Phase 1 Forecast (STAND-IN) | Non-null |
| `valid_time` | Datetime | YYYY-MM-DD HH:MM | Forecast valid timestamp | Timestamp for which forecast applies | Phase 1 Forecast (STAND-IN) | Matches observation_time |
| `lead_time_hours` | Integer | Hours | Forecast lead time | `valid_time` - `forecast_issue_time` | Phase 1 Forecast (STAND-IN) | 24, 48, 72 hours |
| `latitude_obs` | Float | Degrees | Weather station latitude | WGS84 latitude degrees (°N) | Phase 1 Observations | Non-null |
| `longitude_obs` | Float | Degrees | Weather station longitude | WGS84 longitude degrees (°E) | Phase 1 Observations | Non-null |
| `grid_id` | String | None | Nearest 1 km metric grid ID | Spatial join to Phase 2 grid | Phase 2 Grid | Non-null |
| `panchayat_id` | String | None | Gram Panchayat LGD code | Spatial join to Gram Panchayat polygon | Phase 2 Grid | Non-null |
| `forecast_parent_id` | String | None | Coarse forecast parent grid ID | Spatial join to forecast grid point (`FC_GRID_01`...) | Phase 2 Grid | Non-null |
| `station_elevation` | Float | Meters | Ground station elevation | Station metadata elevation in meters | Phase 1 Observations | Default 350.0m |
| `grid_elevation` | Float | Meters | Mean 1 km grid elevation | Phase 2 DEM cell mean elevation | Phase 2 DEM | Non-null |
| `observed_temperature` | Float | °C | Ground observed temperature | Air temperature at 2m height | Phase 1 Observations | Target truth (VALID) |
| `observed_humidity` | Float | % | Ground observed relative humidity | Relative humidity at 2m height | Phase 1 Observations | Target truth (VALID) |
| `observed_rainfall` | Float | mm | Ground observed rainfall | Hourly precipitation amount | Phase 1 Observations | Target truth (VALID) |
| `forecast_temperature` | Float | °C | Coarse forecast temperature | Coarse model temperature at 2m | Phase 1 Forecast (STAND-IN) | Non-null |
| `forecast_humidity` | Float | % | Coarse forecast relative humidity | Coarse model relative humidity at 2m | Phase 1 Forecast (STAND-IN) | Non-null |
| `forecast_rainfall` | Float | mm | Coarse forecast rainfall | Coarse model precipitation amount | Phase 1 Forecast (STAND-IN) | Non-null |
| `b0_temperature` | Float | °C | B0 Coarse Forecast Temperature | Directly equals `forecast_temperature` | Baseline B0 | Non-null |
| `b0_humidity` | Float | % | B0 Coarse Forecast Humidity | Directly equals `forecast_humidity` | Baseline B0 | Non-null |
| `b0_rainfall` | Float | mm | B0 Coarse Forecast Rainfall | Directly equals `forecast_rainfall` | Baseline B0 | Non-null |
| `b1_temperature` | Float | °C | B1 Bilinear Interpolation Temp | 2D Bilinear interpolation from 4 forecast points | Baseline B1 | Fallback to B0 |
| `b1_humidity` | Float | % | B1 Bilinear Interpolation Hum | 2D Bilinear interpolation from 4 forecast points | Baseline B1 | Fallback to B0 |
| `b1_rainfall` | Float | mm | B1 Bilinear Interpolation Rain | 2D Bilinear interpolation from 4 forecast points | Baseline B1 | Fallback to B0 |
| `b1_status` | String | None | B1 Interpolation Status | `INTERPOLATED` or `FALLBACK_B0` | Baseline B1 | Non-null |
| `b2_temperature` | Float | °C | B2 Elevation Corrected Temp | $T_{\text{fc}} + (-0.0065) \times (z_{\text{stn}} - z_{\text{ref}})$ | Baseline B2 | Non-null |
| `b2_humidity` | Float | % | B2 Elevation Corrected Hum | Equals `b0_humidity` (humidity lapse rate N/A) | Baseline B2 | Non-null |
| `b3_temperature` | Float | °C | B3 Quantile Mapped Temp | Quantile mapping fitted strictly on TRAIN split | Baseline B3 | Non-null |
| `b3_humidity` | Float | % | B3 Quantile Mapped Hum | Quantile mapping fitted strictly on TRAIN split | Baseline B3 | Non-null |
| `residual_temperature` | Float | °C | Temperature residual target | `observed_temperature` - `b2_temperature` | Derived for Phase 4 | Non-null |
| `residual_humidity` | Float | % | Humidity residual target | `observed_humidity` - `b0_humidity` | Derived for Phase 4 | Non-null |
| `qc_status` | String | None | Observation quality control flag | `VALID`, `SUSPICIOUS`, `INVALID`, `MISSING` | Phase 1 QC | Non-null |
| `split` | String | None | Chronological temporal split | `TRAIN`, `CALIBRATION`, `TEST` | Temporal Engine | Non-null |
| `data_status` | String | None | Forecast data provenance status | Constant `STAND-IN` | Metadata | Non-null |
