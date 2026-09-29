# Phase 2 Geospatial Grid & Feature Engineering Methodology
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

## 1. Projected Metric CRS Selection

* **Selected Projected CRS:** **EPSG:32643 (WGS 84 / UTM Zone 43N)**
* **Geographic CRS:** EPSG:4326 (WGS 84)
* **Central Meridian:** 75.0° E
* **Latitude Range:** 0° N to 84° N (covers Coimbatore pilot region `10.20°N - 11.40°N, 76.60°E - 77.30°E`)
* **Distance Unit:** Meters ($1\text{ km} = 1000\text{ meters}$)
* **Selection Rationale:** UTM Zone 43N provides a conformal, low-distortion metric coordinate space for Coimbatore (76.6°E - 77.3°E). Generating a "1 km" grid in latitude/longitude degrees is scientifically invalid due to convergence of meridians. Transverse Mercator (EPSG:32643) ensures uniform 1,000m x 1,000m square cell geometry across the entire pilot domain.

---

## 2. 1 km Metric Grid Generation

* **Grid Cell Size:** Exactly $1000\text{ m} \times 1000\text{ m}$ in EPSG:32643.
* **Bounding Box Extent:**
  * **X (Easting):** `674,000.0 m` to `752,000.0 m` (78 columns)
  * **Y (Northing):** `1,127,000.0 m` to `1,262,000.0 m` (135 rows)
* **Total Valid Grid Cells:** **10,530 cells** covering the Coimbatore pilot region.
* **Grid Cell Attributes:**
  * `grid_id`: Unique identifier formatted as `GRID_CBE_00001` through `GRID_CBE_10530`.
  * `centroid_x`, `centroid_y`: Cell centroid coordinates in EPSG:32643 meters.
  * `latitude`, `longitude`: Cell centroid coordinates in EPSG:4326 degrees.
  * `geometry`: Shapely Polygon geometry defining cell boundaries.

---

## 3. Spatial Panchayat Assignment

* **Spatial Join Rule:**
  1. **Primary Rule:** Point-in-polygon containment test checking if cell centroid $(c_x, c_y)$ falls within a Gram Panchayat administrative boundary polygon.
  2. **Fallback Rule:** Nearest Gram Panchayat centroid distance mapping for boundary gap cells.
* **Assigned Attributes:** `panchayat_id`, `panchayat_name`, `block_name`, `district_name`.
* **Diagnostics:**
  * **Cells assigned (centroid contains):** 1,456 cells
  * **Cells assigned (boundary fallback):** 9,074 cells
  * **Panchayats represented:** 180 Gram Panchayats (100% of layer)
  * **Panchayats with zero cells:** 0 Panchayats

---

## 4. Terrain & DEM Feature Engineering

Using the Phase 1 30m Digital Elevation Model GeoTIFF (`coimbatore_dem_30m.tif`):

### Elevation Aggregation
* For each 1 km cell, underlying DEM pixels are extracted to compute:
  * `elevation_mean`: Mean cell elevation (meters)
  * `elevation_std`: Elevation standard deviation / local relief (meters)
  * `elevation_min`, `elevation_max`: Minimum and maximum cell elevation (meters)
  * `elevation_range`: Topographic range ($z_{\max} - z_{\min}$) (meters)

### Slope Algorithm
* Slope is computed using **Horn's 3x3 finite-difference algorithm** on the 30m DEM grid:
  $$\frac{\partial z}{\partial x} = \frac{(z_{1,2} + 2z_{2,2} + z_{3,2}) - (z_{1,0} + 2z_{2,0} + z_{3,0})}{8 \cdot dx}$$
  $$\frac{\partial z}{\partial y} = \frac{(z_{2,0} + 2z_{2,1} + z_{2,2}) - (z_{0,0} + 2z_{0,1} + z_{0,2})}{8 \cdot dy}$$
  $$\text{Slope (degrees)} = \arctan\left(\sqrt{\left(\frac{\partial z}{\partial x}\right)^2 + \left(\frac{\partial z}{\partial y}\right)^2}\right) \times \frac{180}{\pi}$$
* Outputs: `slope_mean`, `slope_std`, `slope_min`, `slope_max` (degrees).

### Aspect Trigonometric Transformation
* Raw aspect angles $[0^\circ, 360^\circ)$ suffer from the 0°/360° discontinuity problem in statistical & ML models.
* Aspect is decomposed into continuous trigonometric components:
  * `aspect_sin` = $\sin(\text{Aspect}_{\text{rad}})$ (North-South aspect component)
  * `aspect_cos` = $\cos(\text{Aspect}_{\text{rad}})$ (East-West aspect component)
  * `aspect_mean_deg` = Mean aspect angle (degrees)
* Flat terrain ($\text{slope} < 0.1^\circ$) has aspect set to 0.

### Terrain Ruggedness Index (TRI)
* Computed according to the **Riley et al. (1999)** formulation:
  $$\text{TRI} = \sqrt{\sum_{i=-1}^{1}\sum_{j=-1}^{1} (z_{i,j} - z_{0,0})^2}$$
* Outputs: `tri_mean`, `tri_std` (meters).

---

## 5. Land Cover Feature Engineering

Using the Phase 1 10m ESA WorldCover LULC raster (`coimbatore_landcover_10m.tif`):

* **Classes Extracted:**
  * 10: Tree cover
  * 20: Shrubland
  * 30: Grassland
  * 40: Cropland
  * 50: Built-up
  * 80: Permanent Water Bodies
* **Outputs:**
  * `dominant_landcover_class`: Dominant class name per cell.
  * Class fractions: `landcover_fraction_tree`, `landcover_fraction_shrub`, `landcover_fraction_grass`, `landcover_fraction_cropland`, `landcover_fraction_builtup`, `landcover_fraction_water`, `nodata_fraction`.
* All fractions sum to 1.0 per grid cell.

---

## 6. Hydrography Distance Engineering

Using Phase 1 water body vector polygons (`coimbatore_water_bodies.geojson`):

* Water geometries (Bhavani River, Noyyal River, Amaravathi River, Aliyar & Siruvani Reservoirs, Lakes) are transformed to EPSG:32643 meters.
* `distance_to_nearest_water`: Minimum Euclidean distance from cell centroid $(c_x, c_y)$ to nearest water polygon boundary (meters).
* **Inland Documentation:** Coimbatore is an inland agricultural district (~100 km inland from Indian Ocean); coastline distance is recorded as not applicable/inland.

---

## 7. Coarse Forecast Grid Alignment

Using Phase 1 historical forecast dataset (`coimbatore_historical_forecasts.csv`, status = **STAND-IN**):

* Sourced from archived operational GFS/ECMWF model runs (Open-Meteo archive), preserving `forecast_issue_time`, `valid_time`, and `lead_time`.
* Identified 12 unique coarse forecast grid points covering the pilot bounding box. Assigned IDs `FC_GRID_01` through `FC_GRID_12`.
* Each 1 km cell centroid is assigned to its nearest coarse forecast parent point in EPSG:32643 meters (`forecast_parent_id`, `distance_to_forecast_grid_m`).

---

## 8. Data Leakage & Future-Model Safety

* All generated geospatial features are strictly static topographic and GIS descriptors.
* No future weather variables, ground station observations, target-day rainfall, target-day temperature, or target-day climatology are included in feature matrices.
