# Phase 2 Geospatial Feature Data Dictionary
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

| Field Name | Data Type | Unit | Meaning | Calculation / Definition | Source Dataset | Missing-Value Handling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `grid_id` | String | None | Unique 1 km cell identifier | Sequential string (`GRID_CBE_00001` ... `GRID_CBE_10530`) | Generator | Primary key (non-null) |
| `centroid_x` | Float | Meters | Projected cell centroid X coordinate | UTM Zone 43N Easting in meters | EPSG:32643 | Non-null |
| `centroid_y` | Float | Meters | Projected cell centroid Y coordinate | UTM Zone 43N Northing in meters | EPSG:32643 | Non-null |
| `latitude` | Float | Degrees | Geographic centroid latitude | WGS84 latitude degrees (°N) | EPSG:4326 | Non-null |
| `longitude` | Float | Degrees | Geographic centroid longitude | WGS84 longitude degrees (°E) | EPSG:4326 | Non-null |
| `min_x` | Float | Meters | West cell boundary coordinate | Centroid X - 500.0m | Grid Generator | Non-null |
| `min_y` | Float | Meters | South cell boundary coordinate | Centroid Y - 500.0m | Grid Generator | Non-null |
| `max_x` | Float | Meters | East cell boundary coordinate | Centroid X + 500.0m | Grid Generator | Non-null |
| `max_y` | Float | Meters | North cell boundary coordinate | Centroid Y + 500.0m | Grid Generator | Non-null |
| `panchayat_id` | String | None | Gram Panchayat LGD code | Spatial join / point-in-polygon assignment | Phase 1 Boundaries | Fallback to nearest GP |
| `panchayat_name` | String | None | Gram Panchayat name | Spatial join / point-in-polygon assignment | Phase 1 Boundaries | Fallback to nearest GP |
| `block_name` | String | None | Administrative block name | Parent block from Panchayat boundary polygon | Phase 1 Boundaries | Non-null |
| `district_name` | String | None | Administrative district name | Constant (`Coimbatore`) | Phase 1 Boundaries | Non-null |
| `elevation_mean` | Float | Meters | Mean elevation in 1 km cell | Mean DEM pixel values inside cell footprint | Phase 1 DEM 30m | Nearest pixel interpolation |
| `elevation_std` | Float | Meters | Elevation standard deviation | Standard deviation of DEM pixels in cell | Phase 1 DEM 30m | Set to 0.0 if flat |
| `elevation_min` | Float | Meters | Minimum elevation in cell | Minimum DEM pixel value inside cell | Phase 1 DEM 30m | Non-null |
| `elevation_max` | Float | Meters | Maximum elevation in cell | Maximum DEM pixel value inside cell | Phase 1 DEM 30m | Non-null |
| `elevation_range` | Float | Meters | Topographic elevation range | $z_{\max} - z_{\min}$ | Derived from DEM | Non-null |
| `slope_mean` | Float | Degrees | Mean terrain slope angle | Mean 3x3 Horn gradient slope in degrees | Derived from DEM | Non-null |
| `slope_std` | Float | Degrees | Slope standard deviation | Standard deviation of slope angles in cell | Derived from DEM | Non-null |
| `slope_min` | Float | Degrees | Minimum slope angle in cell | Minimum slope angle | Derived from DEM | Non-null |
| `slope_max` | Float | Degrees | Maximum slope angle in cell | Maximum slope angle | Derived from DEM | Non-null |
| `aspect_sin` | Float | Unitless | Sine of aspect angle ($\sin\theta$) | Mean $\sin(\text{Aspect}_{\text{rad}})$ component | Derived from DEM | Flat terrain set to 0.0 |
| `aspect_cos` | Float | Unitless | Cosine of aspect angle ($\cos\theta$) | Mean $\cos(\text{Aspect}_{\text{rad}})$ component | Derived from DEM | Flat terrain set to 0.0 |
| `aspect_mean_deg` | Float | Degrees | Mean raw aspect angle | Mean aspect angle in degrees $[0^\circ, 360^\circ)$ | Derived from DEM | Flat terrain set to 0.0 |
| `tri_mean` | Float | Meters | Mean Terrain Ruggedness Index | Riley et al. (1999) 3x3 TRI formula | Derived from DEM | Non-null |
| `tri_std` | Float | Meters | TRI standard deviation | Standard deviation of TRI inside cell | Derived from DEM | Non-null |
| `dominant_landcover_class` | String | None | Dominant LULC class name | Most frequent class in cell footprint | Phase 1 Land Cover 10m | Default `Cropland` |
| `landcover_fraction_tree` | Float | Ratio | Tree cover area fraction | Pixels with class 10 / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `landcover_fraction_shrub` | Float | Ratio | Shrubland area fraction | Pixels with class 20 / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `landcover_fraction_grass` | Float | Ratio | Grassland area fraction | Pixels with class 30 / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `landcover_fraction_cropland` | Float | Ratio | Cropland area fraction | Pixels with class 40 / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `landcover_fraction_builtup` | Float | Ratio | Built-up area fraction | Pixels with class 50 / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `landcover_fraction_water` | Float | Ratio | Water surface area fraction | Pixels with class 80 / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `nodata_fraction` | Float | Ratio | Nodata pixel fraction | Nodata pixels / total cell pixels | Phase 1 Land Cover 10m | 0.0 if absent |
| `distance_to_nearest_water` | Float | Meters | Distance to nearest water body | Euclidean distance in EPSG:32643 meters | Phase 1 Water Hydro | Non-null |
| `forecast_parent_id` | String | None | Parent coarse forecast grid ID | Nearest neighbor mapping (`FC_GRID_01` ...) | Phase 1 Forecast (STAND-IN) | Non-null |
| `distance_to_forecast_grid_m` | Float | Meters | Distance to forecast grid point | Euclidean distance to forecast parent (meters) | Phase 1 Forecast (STAND-IN) | Non-null |
