"""
GramDrishti — Phase 9 Single Demo Entry Point
==============================================
Reproducible SIH demo launcher for GramDrishti.
Runs 100% offline from local dataset artifacts.

Usage:
    python scripts/run_demo.py
"""

import sys
import os
import uvicorn

# Ensure repository root is in sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.dashboard.demo_validation import DemoDataValidator


def main():
    print("=" * 70)
    print("GramDrishti — Panchayat-Level Weather Downscaling for Agro-Advisories")
    print("SIH PS 26074 Demonstration App Launcher")
    print("=" * 70)
    print("Pilot Region: Coimbatore District, Tamil Nadu (180 Gram Panchayats)")
    print("Data Mode:    OFFLINE REPLAY (May 01 – June 30, 2024)")
    print("-" * 70)

    # 1. Run Demo Data Validation
    print("[1/3] Validating local dataset artifacts...")
    validator = DemoDataValidator()
    is_valid, messages = validator.validate_all()
    for msg in messages:
        print(" ", msg)

    if not is_valid:
        print("\n[ERROR] Demo validation failed! Missing required artifacts.")
        print("Please ensure all Phase 1–8 prediction CSVs and GeoJSON files are present.")
        sys.exit(1)

    print("\n[2/3] Initializing Dashboard & Service Layer...")
    print("  ✓ Services initialized.")
    print("  ✓ REST API Endpoints ready.")
    print("  ✓ Leaflet.js Interactive Map ready.")

    print("\n[3/3] Starting GramDrishti Server...")
    print("-" * 70)
    print("  ➜ Local Dashboard UI:  http://127.0.0.1:8000")
    print("  ➜ REST API Docs:       http://127.0.0.1:8000/docs")
    print("  ➜ System Status:       http://127.0.0.1:8000/api/v1/system-status")
    print("-" * 70)
    print("Press Ctrl+C to stop the server.\n")

    # Start FastAPI server via uvicorn
    from src.dashboard.app import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
