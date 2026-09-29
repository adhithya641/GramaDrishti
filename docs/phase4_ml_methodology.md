# Phase 4 LightGBM Residual Correction Methodology
## GramDrishti — SIH PS 26074 (Panchayat-Level Weather Downscaling)

---

## 1. Executive Overview

Phase 4 implements a **LightGBM Gradient Boosted Decision Tree (GBDT) residual-correction model** for temperature and relative humidity. Rather than attempting to predict raw atmospheric state variables directly from high-dimensional predictors, the model predicts the **residual offset** relative to the physics-based elevation lapse-rate baseline (**B2**).

$$\text{residual}_{\text{target}} = \text{observation} - \text{B2}_{\text{prediction}}$$

$$\text{ML}_{\text{corrected}} = \text{B2}_{\text{prediction}} + \hat{\text{residual}}_{\text{ML}}$$

This approach enforces physical sanity via B2 elevation corrections while allowing LightGBM to learn non-linear microclimatic refinements from terrain, land cover, water proximity, and temporal cycles.

---

## 2. Feature Architecture & Leakage Prevention

### 2.1 Feature Inclusion Matrix

The feature matrix $X$ strictly consumes information legitimately available at forecast time:

| Domain | Feature Name | Type | Description |
| :--- | :--- | :--- | :--- |
| **Forecast** | `forecast_temperature` | Float | Coarse model issue temperature |
| **Forecast** | `forecast_humidity` | Float | Coarse model issue relative humidity |
| **Forecast** | `forecast_rainfall` | Float | Coarse model issue rainfall |
| **Forecast** | `lead_time_hours` | Int | Forecast horizon (24h, 48h, 72h) |
| **Baseline** | `b2_temperature` / `b2_humidity` | Float | Elevation lapse-rate baseline prediction |
| **Geospatial** | `elevation_mean`, `elevation_std`, `elevation_range` | Float | 1 km grid DEM terrain features |
| **Geospatial** | `slope_mean`, `slope_std` | Float | Surface slope statistics |
| **Geospatial** | `aspect_sin`, `aspect_cos` | Float | Aspect direction components |
| **Geospatial** | `tri_mean`, `tri_std` | Float | Terrain Ruggedness Index |
| **Geospatial** | `dominant_landcover_class` | Categorical | WorldCover land cover class |
| **Geospatial** | `landcover_fraction_*` | Float | Fractions of tree, shrub, grass, crop, builtup, water |
| **Geospatial** | `distance_to_nearest_water` | Float | Distance to nearest water body (m) |
| **Geometry** | `distance_to_forecast_grid_m` | Float | Distance to parent forecast grid point (m) |
| **Temporal** | `day_of_year_sin`, `day_of_year_cos` | Float | Cyclical seasonal encoding |
| **Temporal** | `month` | Int | Month index (1–12) |

### 2.2 Strictly Forbidden Features (Leakage Guard)

To prevent target memorization, spatial overfitting, and future leakage, the following variables are **strictly prohibited** from the feature matrix:

1. **`station_id` & `station_group`**: Preserved strictly for Leave-One-Station-Out (LOSO) grouping and evaluation. Never encoded as a model feature.
2. **Station Coordinates (`latitude_obs`, `longitude_obs`)**: Omitted to prevent memorizing fixed station locations. All spatial intelligence is derived strictly from 1 km grid GIS features.
3. **Ground Observations (`observed_*`)**: Forbidden to prevent target contamination.
4. **Target Residuals (`residual_*`)**: Forbidden.
5. **Baselines B0, B1, B3**: Excluded to ensure ML evaluates independently against B2 residual learning.

---

## 3. Categorical Variable Handling

`dominant_landcover_class` is formatted as pandas `Categorical` dtype and passed directly to LightGBM's native categorical splitting mechanism (`categorical_feature=['dominant_landcover_class']`). This avoids imposing arbitrary numeric ordinality.

---

## 4. Deterministic Temporal Partitioning

Data splitting strictly preserves chronological order to simulate operational deployment:

- **TRAIN:** `2024-01-01` → `2024-03-31` (50% of timeline, 2,136 records)
- **CALIBRATION:** `2024-04-01` → `2024-04-30` (17% of timeline, 720 records)
- **TEST (Held-Out):** `2024-05-01` → `2024-06-30` (33% of timeline, 1,464 records)

The **TEST** set remains completely untouched during model training, feature selection, and hyperparameter configuration.

---

## 5. LightGBM Configuration

Models are trained using a transparent CPU configuration:

```yaml
objective: "regression"
metric: "rmse"
learning_rate: 0.05
n_estimators: 100
max_depth: 5
num_leaves: 15
min_child_samples: 10
subsample: 0.8
colsample_bytree: 0.8
random_state: 42
```

---

## 6. Scientific Evaluation Rules

The ML model is evaluated against the complete baseline ladder:
- **B0:** Coarse forecast
- **B1:** Bilinear spatial interpolation
- **B2:** Elevation lapse-rate correction
- **B3:** Empirical quantile mapping (fitted on TRAIN)
- **ML:** LightGBM residual correction ($B2 + \hat{\text{residual}}$)

Skill improvement is computed against both B2 and B3:

$$\text{Improvement}_{\%} = 100 \times \frac{\text{MAE}_{\text{baseline}} - \text{MAE}_{\text{ML}}}{\text{MAE}_{\text{baseline}}}$$

Negative values indicate performance regression and are reported transparently.
