# GramDrishti — Phase 1 Setup Guide
## SIH PS 26074: Panchayat-Level Weather Downscaling for Agro-Advisories

---

## Prerequisites

- Python 3.10 or later
- pip

## Installation

```bash
cd d:\GramDrishti
python -m pip install -r requirements.txt
```

---

## Project Structure

```
GramDrishti/
├── configs/
│   ├── data_sources.yaml          # Data source configuration
│   └── metadata_schema.yaml       # Metadata schema definition
│
├── data/
│   ├── raw/                       # Original data (NEVER overwritten)
│   │   ├── boundaries/
│   │   ├── observations/
│   │   ├── forecasts/
│   │   ├── dem/
│   │   ├── landcover/
│   │   └── water/
│   ├── interim/                   # Intermediate processing
│   ├── processed/                 # Validated + cleaned data
│   │   ├── boundaries/
│   │   ├── observations/
│   │   ├── forecasts/
│   │   ├── dem/
│   │   ├── landcover/
│   │   └── water/
│   └── metadata/                  # Validation reports + metadata JSONs
│
├── src/
│   ├── ingestion/                 # Data ingestion modules
│   │   ├── validation_utils.py    # Shared validation framework
│   │   ├── boundaries.py          # Panchayat boundary ingestion
│   │   ├── observations.py        # Weather station observations
│   │   ├── forecasts.py           # Weather forecast ingestion
│   │   ├── dem.py                 # DEM raster ingestion
│   │   ├── landcover.py           # LULC ingestion
│   │   ├── water.py               # Water/coast ingestion
│   │   └── validate_dataset.py    # CLI validator
│   ├── preprocessing/             # (Phase 2)
│   └── geospatial/                # (Phase 2)
│
├── tests/                         # Pytest test suite
├── docs/                          # Documentation
├── logs/                          # Log files
└── requirements.txt
```

---

## Running Validation

### Validate the configuration itself

```bash
python -m src.ingestion.validate_dataset --validate-config
```

### Validate a single dataset

```bash
python -m src.ingestion.validate_dataset --source observations --input data/raw/observations/my_data.csv
```

### Validate all data files

```bash
python -m src.ingestion.validate_dataset --validate-all
```

### JSON output (for scripting)

```bash
python -m src.ingestion.validate_dataset --validate-config --json
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Adding Data

1. Place raw data files in the appropriate `data/raw/<type>/` directory.
2. **Never** modify files in `data/raw/` after placement.
3. Run the appropriate ingestor or `--validate-all`.
4. Check `data/metadata/` for validation reports.
5. Check `data/processed/<type>/` for cleaned output.

---

## Data Provenance Rules

- **REAL**: Official data from verified sources only.
- **SYNTHETIC**: Clearly labelled test data.
- **PLACEHOLDER**: Schema-correct but no real values.
- **STAND-IN**: Proxy from alternative sources.
- **UNVERIFIED**: Source not independently confirmed.
- **UNAVAILABLE**: Not yet acquired.

**Never label synthetic or stand-in data as REAL.**
