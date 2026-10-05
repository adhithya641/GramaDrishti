"""
GramDrishti — Phase 11 Video-Aligned Demo Launcher
===================================================
Reproducible SIH jury demonstration app launcher for GramDrishti.
Supports 🟢 LIVE MODE (Open-Meteo real-time regional weather) and
📜 HISTORICAL REPLAY MODE (180 Gram Panchayats downscaled model).

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
from src.ingestion.live_weather import fetch_live_weather


def print_demo_workflow():
    """Display the 17-step SIH jury demonstration workflow script."""
    print("\n" + "=" * 75)
    print("      SIH JURY DEMONSTRATION WORKFLOW (17 STEPS ALIGNED WITH VIDEO)")
    print("=" * 75)
    steps = [
        ("1. Open Application", "Launch prototype server at http://127.0.0.1:8000"),
        ("2. Default Live Mode", "🟢 LIVE MODE initializes by default on startup"),
        ("3. Current Weather", "Displays live real-time Coimbatore regional weather"),
        ("4. Provenance & Source", "Shows Open-Meteo data source, fetch timestamp, and data age"),
        ("5. Mode Switcher", "Click toggle to switch to 📜 HISTORICAL REPLAY MODE"),
        ("6. District Map", "Displays 180 Gram Panchayats interactive Leaflet map mesh"),
        ("7. Panchayat Selection", "Click any Panchayat polygon (e.g., TN_CBE_001 / Anaimalai)"),
        ("8. Local Downscaling", "Displays local temperature & humidity downscaled predictions"),
        ("9. CQR Uncertainty", "Displays P10 / P50 / P90 non-parametric confidence bounds"),
        ("10. Reliability Badge", "Shows evidence-based reliability classification badge"),
        ("11. Fallback Logic", "Exposes automated quality gating & fallback triggers"),
        ("12. Agro-Advisories", "Displays context-aware, gated agricultural advisories"),
        ("13. Validation Audit", "Presents held-out test evaluation metrics (Jan–Jun 2024)"),
        ("14. Held-out Split", "Explains 60/20/20 spatial-temporal dataset partition"),
        ("15. Temperature Honesty", "Highlights GIS elevation did NOT improve Temp (1.08°C vs 1.22°C)"),
        ("16. Humidity Improvement", "Highlights GIS land cover DID improve Humidity (20.09% vs 19.46%)"),
        ("17. Live Mode Return", "Toggle back to 🟢 LIVE MODE — zero state contamination"),
    ]
    for idx, (title, detail) in enumerate(steps, 1):
        print(f"  Step {idx:02d}: {title:<22} -> {detail}")
    print("=" * 75 + "\n")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 75)
    print("GramDrishti — Terrain-Aware Panchayat Weather Downscaling Platform")
    print("SIH PS 26074 Demonstration App Launcher")
    print("=" * 75)
    print("Pilot Region:  Coimbatore District, Tamil Nadu (180 Gram Panchayats)")
    print("Data Modes:    🟢 LIVE MODE (Open-Meteo) | 📜 HISTORICAL REPLAY (May–Jun 2024)")
    print("-" * 75)

    # 1. Run Demo Data Validation
    print("[1/4] Validating local dataset artifacts & scientific freeze...")
    validator = DemoDataValidator()
    is_valid, messages = validator.validate_all()
    for msg in messages:
        print(" ", msg)

    if not is_valid:
        print("\n[ERROR] Demo validation failed! Missing required artifacts.")
        print("Please ensure all Phase 1–8 prediction CSVs and GeoJSON files are present.")
        sys.exit(1)

    # 2. Live Network Connectivity Check
    print("\n[2/4] Testing real-time Open-Meteo weather connection...")
    live_res = fetch_live_weather(use_cache_on_failure=True)
    if live_res["status"] == "live":
        d = live_res["data"]
        print(f"  [OK] Open-Meteo API Connected: Coimbatore {d['temperature_c']}°C, {d['relative_humidity_pct']}% RH ({d['weather_description']})")
    elif live_res["status"] == "cached":
        print(f"  [WARN] Open-Meteo API offline/unreachable. Using cached live weather ({live_res.get('cache_age_seconds')}s old).")
    else:
        print(f"  [WARN] Open-Meteo API offline. Falling back to Historical Replay mode.")

    # 3. Print Demonstration Workflow Script
    print("\n[3/4] Preparing Demonstration Workflow Script...")
    print_demo_workflow()

    # 4. Start FastAPI Server
    print("[4/4] Starting GramDrishti Server...")
    print("-" * 75)
    print("  ➜ Local Dashboard UI:  http://127.0.0.1:8000")
    print("  ➜ REST API Docs:       http://127.0.0.1:8000/docs")
    print("  ➜ System Status:       http://127.0.0.1:8000/api/v1/system-status")
    print("  ➜ Live Weather API:    http://127.0.0.1:8000/api/live/weather")
    print("-" * 75)
    print("Press Ctrl+C to stop the server.\n")

    # Start FastAPI server via uvicorn
    from src.dashboard.app import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
