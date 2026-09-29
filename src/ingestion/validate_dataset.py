"""
GramDrishti -- Dataset Validator CLI
=======================================
Standalone entry-point for validating any dataset by source key.

Usage:
  python -m src.ingestion.validate_dataset --source observations --input data/raw/observations/stations.csv
  python -m src.ingestion.validate_dataset --validate-all
  python -m src.ingestion.validate_dataset --validate-config
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict

import yaml

from src.ingestion.validation_utils import load_config, get_project_root

logger = logging.getLogger("gramdrishti.validate")

# Registry: source_key -> (module_path, class_name)
INGESTOR_REGISTRY = {
    "boundaries":   ("src.ingestion.boundaries",   "BoundaryIngestor"),
    "observations": ("src.ingestion.observations",  "ObservationIngestor"),
    "forecasts":    ("src.ingestion.forecasts",     "ForecastIngestor"),
    "dem":          ("src.ingestion.dem",            "DEMIngestor"),
    "landcover":    ("src.ingestion.landcover",     "LandcoverIngestor"),
    "water":        ("src.ingestion.water",         "WaterIngestor"),
}


def _import_ingestor(source_key: str):
    """Dynamically import the ingestor class for a given source key."""
    if source_key not in INGESTOR_REGISTRY:
        raise ValueError(
            f"Unknown source key '{source_key}'. "
            f"Must be one of: {list(INGESTOR_REGISTRY.keys())}"
        )
    module_path, class_name = INGESTOR_REGISTRY[source_key]
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def validate_dataset(
    source_key: str,
    input_path: str | Path,
    config_path: str | Path | None = None,
) -> dict:
    """Validate a single dataset and return the report dict."""
    cls = _import_ingestor(source_key)
    ingestor = cls(input_path=input_path, config_path=config_path)
    report = ingestor.run()
    return report.to_dict()


def validate_all(config_path: str | Path | None = None) -> Dict[str, list]:
    """Scan all raw directories and validate any data files found."""
    project_root = get_project_root()
    config = load_config(config_path)
    results: Dict[str, list] = {}

    for source_key, source_cfg in config["data_sources"].items():
        raw_dir = project_root / source_cfg.get("local_path", source_cfg.get("raw_dir", ""))
        results[source_key] = []
        if not raw_dir.exists():
            logger.warning("Raw directory missing: %s", raw_dir)
            continue

        expected_exts = [f".{e.lower()}" for e in source_cfg.get("format", [])]
        files = [
            f for f in raw_dir.iterdir()
            if f.is_file() and f.suffix.lower() in expected_exts and f.name != ".gitkeep"
        ]
        if not files:
            logger.info("No data files in %s", raw_dir)
            continue

        for filepath in files:
            logger.info("Validating %s / %s", source_key, filepath.name)
            try:
                summary = validate_dataset(source_key, filepath, config_path)
                results[source_key].append(summary)
            except Exception as exc:
                logger.error("Failed: %s: %s", filepath, exc)
                results[source_key].append({
                    "dataset_name": source_key,
                    "file": str(filepath),
                    "error": str(exc),
                })
    return results


def validate_config(config_path: str | Path | None = None) -> dict:
    """Validate the data_sources.yaml configuration itself."""
    project_root = get_project_root()
    config = load_config(config_path)

    report = {
        "config_file": str(config_path or "configs/data_sources.yaml"),
        "project_name": config.get("project", {}).get("name", "UNKNOWN"),
        "pilot_region": config.get("pilot_region", {}).get("status", "UNKNOWN"),
        "sources_defined": [],
        "directories_status": {},
        "issues": [],
    }

    for source_key, source_cfg in config.get("data_sources", {}).items():
        report["sources_defined"].append(source_key)
        raw_dir = project_root / source_cfg.get("local_path", source_cfg.get("raw_dir", ""))
        proc_dir = project_root / source_cfg.get("processed_dir", "")

        raw_files = 0
        if raw_dir.exists():
            raw_files = len([f for f in raw_dir.iterdir()
                           if f.is_file() and f.name != ".gitkeep"])

        report["directories_status"][source_key] = {
            "raw_dir": str(raw_dir),
            "raw_exists": raw_dir.exists(),
            "raw_file_count": raw_files,
            "processed_dir": str(proc_dir),
            "processed_exists": proc_dir.exists(),
            "status": source_cfg.get("status", "UNKNOWN"),
        }
        if not source_cfg.get("required_fields") and not source_cfg.get("format"):
            report["issues"].append(f"{source_key}: incomplete configuration")

    return report


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="GramDrishti Dataset Validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--source", type=str, help="Source key")
    parser.add_argument("--input", type=str, help="Path to input data file")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--validate-all", action="store_true")
    parser.add_argument("--validate-config", action="store_true")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.validate_config:
        result = validate_config(args.config)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print("=== Configuration Validation ===")
            print(f"  Project      : {result['project_name']}")
            print(f"  Pilot Region : {result['pilot_region']}")
            print(f"  Sources      : {result['sources_defined']}")
            for src, st in result["directories_status"].items():
                raw_ok = "[OK]" if st["raw_exists"] else "[MISSING]"
                print(f"  {src}: raw {raw_ok} ({st['raw_file_count']} files), status={st['status']}")
            if result["issues"]:
                print("  Issues:")
                for issue in result["issues"]:
                    print(f"    [!] {issue}")
        return

    if args.validate_all:
        results = validate_all(args.config)
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print("=== Validate All ===")
            for source_key, summaries in results.items():
                if not summaries:
                    print(f"  {source_key}: (no data files found)")
                for s in summaries:
                    valid = s.get("is_valid", False)
                    status = "[VALID]" if valid else "[INVALID]"
                    print(f"  {source_key}: {status}")
        return

    if args.source and args.input:
        result = validate_dataset(args.source, args.input, args.config)
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(json.dumps(result, indent=2, default=str))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
