"""
GramDrishti -- Common Validation Utilities
============================================
Reusable validation helpers shared across all ingestion modules.

Reports:
  DATASET, SOURCE, STATUS, FORMAT, CRS, SPATIAL EXTENT, TEMPORAL EXTENT,
  RECORD/FEATURE COUNT, RESOLUTION, MISSINGNESS, KNOWN LIMITATIONS

Uses structured logs. Never silently repairs problems.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger("gramdrishti.validation")


# ---- Config loader --------------------------------------------------------

def load_config(config_path: str | Path | None = None) -> dict:
    """Load configs/data_sources.yaml from the project root."""
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "configs" / "data_sources.yaml"
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


# ---- Validation Report ----------------------------------------------------

class ValidationReport:
    """
    Structured validation report for a single dataset ingestion run.

    Accumulates checks and produces a serialisable summary dict
    that can be saved to JSON and printed to the console.
    """

    def __init__(self, dataset_name: str, source_key: str):
        self.dataset_name = dataset_name
        self.source_key = source_key
        self.timestamp = datetime.now(timezone.utc).isoformat()

        # Core metrics
        self.source: str = "UNKNOWN"
        self.status: str = "PENDING"  # READY / PARTIAL / MISSING / UNVERIFIED
        self.file_format: Optional[str] = None
        self.crs_detected: Optional[str] = None
        self.spatial_extent: Optional[Dict[str, float]] = None
        self.temporal_extent: Optional[Dict[str, str]] = None
        self.record_count: int = 0
        self.resolution: Optional[str] = None

        # Field validation
        self.fields_present: List[str] = []
        self.fields_missing: List[str] = []

        # Missing-value tracking
        self.missing_value_counts: Dict[str, int] = {}
        self.missing_value_percentages: Dict[str, float] = {}

        # Issues
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.limitations: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.error("[%s] %s", self.source_key, msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("[%s] %s", self.source_key, msg)

    def add_limitation(self, msg: str) -> None:
        self.limitations.append(msg)
        logger.info("[%s] LIMITATION: %s", self.source_key, msg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "source_key": self.source_key,
            "timestamp": self.timestamp,
            "source": self.source,
            "status": self.status,
            "is_valid": self.is_valid,
            "file_format": self.file_format,
            "crs_detected": self.crs_detected,
            "spatial_extent": self.spatial_extent,
            "temporal_extent": self.temporal_extent,
            "record_count": self.record_count,
            "resolution": self.resolution,
            "fields_present": self.fields_present,
            "fields_missing": self.fields_missing,
            "missing_value_counts": self.missing_value_counts,
            "missing_value_percentages": self.missing_value_percentages,
            "warnings": self.warnings,
            "errors": self.errors,
            "limitations": self.limitations,
        }

    def print_report(self) -> str:
        """Human-readable summary for console output."""
        lines = [
            f"{'='*60}",
            f"  VALIDATION REPORT: {self.dataset_name}",
            f"{'='*60}",
            f"  Source Key    : {self.source_key}",
            f"  Source        : {self.source}",
            f"  Status        : {self.status}",
            f"  Valid          : {self.is_valid}",
            f"  Timestamp      : {self.timestamp}",
            f"  Format         : {self.file_format or 'N/A'}",
            f"  CRS            : {self.crs_detected or 'N/A'}",
            f"  Record Count   : {self.record_count}",
            f"  Resolution     : {self.resolution or 'N/A'}",
        ]
        if self.spatial_extent:
            se = self.spatial_extent
            lines.append(
                f"  Spatial Extent : lat [{se.get('min_lat')}, {se.get('max_lat')}] "
                f"lon [{se.get('min_lon')}, {se.get('max_lon')}]"
            )
        if self.temporal_extent:
            te = self.temporal_extent
            lines.append(
                f"  Temporal Extent: {te.get('start_date', '?')} to {te.get('end_date', '?')}"
            )
        if self.fields_present:
            lines.append(f"  Fields Present : {self.fields_present}")
        if self.fields_missing:
            lines.append(f"  Fields Missing : {self.fields_missing}")
        if self.missing_value_counts:
            lines.append("  Missing Values :")
            for col, cnt in self.missing_value_counts.items():
                pct = self.missing_value_percentages.get(col, 0)
                lines.append(f"    {col}: {cnt} ({pct:.1f}%)")
        if self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append(f"    [WARN] {w}")
        if self.errors:
            lines.append("  Errors:")
            for e in self.errors:
                lines.append(f"    [ERROR] {e}")
        if self.limitations:
            lines.append("  Known Limitations:")
            for lim in self.limitations:
                lines.append(f"    [LIMIT] {lim}")
        lines.append(f"{'='*60}")
        return "\n".join(lines)


# ---- Common validation functions ------------------------------------------

def validate_file_exists(path: Path) -> Tuple[bool, str]:
    """Check that a file or directory exists."""
    if not path.exists():
        return False, f"Path does not exist: {path}"
    return True, f"Path verified: {path}"


def check_required_fields(
    available_columns: List[str],
    required_fields: List[str],
    case_insensitive: bool = True,
) -> Tuple[List[str], List[str]]:
    """Return (present, missing) lists for required field names."""
    if case_insensitive:
        avail_lower = {c.lower(): c for c in available_columns}
        present = [f for f in required_fields if f.lower() in avail_lower]
        missing = [f for f in required_fields if f.lower() not in avail_lower]
    else:
        present = [f for f in required_fields if f in available_columns]
        missing = [f for f in required_fields if f not in available_columns]
    return present, missing


def compute_missing_stats(
    data_dict: Dict[str, Any],
    total: int,
) -> Tuple[Dict[str, int], Dict[str, float]]:
    """
    Compute missing-value counts and percentages.

    Parameters
    ----------
    data_dict : dict
        Maps column name -> count of missing values.
    total : int
        Total number of records.

    Returns
    -------
    (counts, percentages)
    """
    counts = {}
    pcts = {}
    for col, n_missing in data_dict.items():
        if n_missing > 0:
            counts[col] = n_missing
            pcts[col] = round(n_missing / total * 100, 2) if total > 0 else 0.0
    return counts, pcts


def validate_coordinates_india(
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float,
    config: dict,
) -> List[str]:
    """Check if coordinates fall within India bounds from config."""
    warnings = []
    bounds = config.get("validation", {}).get("coordinate_bounds", {})
    if not bounds:
        return warnings
    if lat_min < bounds.get("india_lat_min", 6):
        warnings.append(f"min_lat {lat_min} is below India south bound")
    if lat_max > bounds.get("india_lat_max", 38):
        warnings.append(f"max_lat {lat_max} is above India north bound")
    if lon_min < bounds.get("india_lon_min", 68):
        warnings.append(f"min_lon {lon_min} is west of India west bound")
    if lon_max > bounds.get("india_lon_max", 98):
        warnings.append(f"max_lon {lon_max} is east of India east bound")
    return warnings


def apply_column_mapping(
    df,
    column_mapping: Dict[str, str],
):
    """
    Rename DataFrame columns using a configurable mapping.
    Only renames columns that exist in the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The dataframe to rename.
    column_mapping : dict
        Maps canonical name -> actual column name in the raw data.

    Returns
    -------
    pd.DataFrame with renamed columns.
    """
    # Invert: actual_name -> canonical_name
    reverse_map = {v: k for k, v in column_mapping.items() if v != k}
    existing = {v: k for v, k in reverse_map.items() if v in df.columns}
    if existing:
        df = df.rename(columns=existing)
        logger.info("Column mapping applied: %s", existing)
    return df


def find_column(df, name: str) -> Optional[str]:
    """Case-insensitive column lookup in a DataFrame."""
    for col in df.columns:
        if col.lower() == name.lower():
            return col
    return None


# ---- Metadata generation --------------------------------------------------

def generate_metadata(
    source_key: str,
    report: ValidationReport,
    source_config: dict,
    data_provenance: str = "UNAVAILABLE",
) -> dict:
    """
    Generate a metadata record for a dataset.

    Parameters
    ----------
    source_key : str
        Dataset key (boundaries, observations, etc.).
    report : ValidationReport
        Completed validation report.
    source_config : dict
        The source configuration from data_sources.yaml.
    data_provenance : str
        One of: REAL, SYNTHETIC, PLACEHOLDER, STAND-IN, UNVERIFIED, UNAVAILABLE.
    """
    return {
        "dataset_name": report.dataset_name,
        "source": source_config.get("source", "UNKNOWN"),
        "source_url": source_config.get("source_url", "UNKNOWN"),
        "download_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "original_filename": "",
        "format": report.file_format or "UNKNOWN",
        "crs": report.crs_detected or "UNKNOWN",
        "resolution": report.resolution or "UNKNOWN",
        "geographic_coverage": source_config.get("geographic_coverage", "UNKNOWN"),
        "temporal_coverage": report.temporal_extent or "UNKNOWN",
        "variables": report.fields_present,
        "record_count": report.record_count,
        "processing_status": report.status,
        "data_status": data_provenance,
        "limitations": report.limitations,
        "notes": source_config.get("notes", ""),
        "validation_summary": report.to_dict(),
    }


def save_report(report: ValidationReport, output_dir: Path | None = None) -> Path:
    """Save a validation report as JSON to data/metadata/."""
    if output_dir is None:
        output_dir = get_project_root() / "data" / "metadata"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"validation_{report.source_key}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, indent=2, default=str)
    logger.info("Validation report saved: %s", path)
    return path


def save_metadata(meta: dict, source_key: str, output_dir: Path | None = None) -> Path:
    """Save a metadata record as JSON to data/metadata/."""
    if output_dir is None:
        output_dir = get_project_root() / "data" / "metadata"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"metadata_{source_key}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)
    logger.info("Metadata saved: %s", path)
    return path
