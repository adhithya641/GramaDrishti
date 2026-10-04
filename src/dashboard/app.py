"""
GramDrishti — Phase 8 / Phase 10A FastAPI Application Server
=============================================================
REST API & Interactive Dashboard server for SIH demonstration.
Supports LIVE weather mode (Open-Meteo) and HISTORICAL REPLAY mode.
"""

import os
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.dashboard.service import DashboardDataService
from src.ingestion.live_weather import fetch_live_weather, get_freshness_status
from src.ingestion.live_validator import validate_live_weather, get_mode_label

app = FastAPI(
    title="GramDrishti API",
    description="Terrain-Aware Panchayat Weather Downscaling & Agro-Advisory API",
    version="1.0.0"
)

# Initialize service layer
service = DashboardDataService()

# Serve static directory if it exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse)
def root_dashboard():
    """Serve the main interactive GramDrishti prototype dashboard."""
    index_html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_html_path):
        with open(index_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>GramDrishti Dashboard API</h1><p>Static index.html loading...</p>")


# ─── System / Meta ───────────────────────────────────────────────────────────

@app.get("/api/health")
def get_health():
    """Health check endpoint — returns current system mode and live status."""
    result = fetch_live_weather()
    live_data = result.get("data")
    freshness = get_freshness_status(live_data["data_age_seconds"]) if live_data else "UNAVAILABLE"
    mode_label = get_mode_label(result["status"], freshness)
    return {
        "status": "ok",
        "mode": result["status"],
        "mode_label": mode_label,
        "source": "Open-Meteo",
        "freshness": freshness,
        "timestamp": live_data["timestamp"] if live_data else None,
        "error": result.get("error"),
    }


@app.get("/api/v1/system-status")
def get_system_status():
    """Return runtime system health and data status checks."""
    return service.get_system_status()


@app.get("/api/v1/metadata")
def get_metadata():
    """Return metadata summary and validation timestamp."""
    return {
        "project": "GramDrishti",
        "phase": "10B",
        "pilot_region": "Coimbatore, Tamil Nadu",
        "panchayats_count": 180,
        "grid_resolution": "1 km",
        "default_mode": "LIVE",
        "data_modes": ["LIVE", "HISTORICAL REPLAY"],
        "live_provider": "Open-Meteo (no API key required)",
        "disclaimer": "GramDrishti is a validation-driven correction layer over coarse weather forecasts. It does not replace operational forecasts or establish panchayat-scale ground truth."
    }


@app.get("/api/v1/timestamps")
def get_timestamps():
    """Return available forecast timestamps for historical replay mode."""
    return {
        "timestamps": service.get_available_timestamps(),
        "lead_times": service.get_available_lead_times()
    }


@app.get("/api/v1/panchayats")
def get_panchayats():
    """Return list of all Gram Panchayats with block metadata and cell count."""
    return {
        "panchayats": service.get_panchayat_list()
    }


@app.get("/api/v1/geojson")
def get_geojson(
    timestamp: Optional[str] = Query(None, description="Forecast timestamp (YYYY-MM-DD)"),
    variable: str = Query("temperature", description="Variable: temperature, humidity, rain_1mm, rain_10mm, rain_25mm"),
    lead_time: int = Query(24, description="Forecast lead time in hours (24, 48, 72)")
):
    """Return GeoJSON FeatureCollection with downscaled prediction properties for map rendering."""
    return service.get_geojson_with_predictions(
        timestamp=timestamp,
        variable=variable,
        lead_time=lead_time
    )


# ─── Panchayat endpoints ──────────────────────────────────────────────────────

@app.get("/panchayat/{panchayat_id}/forecast")
@app.get("/api/v1/panchayat/{panchayat_id}/forecast")
def get_panchayat_forecast(
    panchayat_id: str,
    timestamp: Optional[str] = Query(None),
    lead_time: int = Query(24)
):
    """Return detailed forecast for a single Gram Panchayat."""
    detail = service.get_panchayat_detail(
        panchayat_id=panchayat_id,
        timestamp=timestamp,
        lead_time=lead_time
    )
    return detail


@app.get("/panchayat/{panchayat_id}/reliability")
@app.get("/api/v1/panchayat/{panchayat_id}/reliability")
def get_panchayat_reliability(
    panchayat_id: str,
    timestamp: Optional[str] = Query(None),
    lead_time: int = Query(24)
):
    """Return Phase 7 evidence-based reliability report for a Gram Panchayat."""
    detail = service.get_panchayat_detail(
        panchayat_id=panchayat_id,
        timestamp=timestamp,
        lead_time=lead_time
    )
    return {
        "panchayat_id": detail["panchayat_id"],
        "timestamp": detail["timestamp"],
        "lead_time": detail["lead_time"],
        "reliability": detail["reliability"],
        "reasons": detail["reasons"],
        "freshness": detail["freshness"],
        "fallback": detail["fallback"],
        "location": detail["location"]
    }


@app.get("/panchayat/{panchayat_id}/advisory")
@app.get("/api/v1/panchayat/{panchayat_id}/advisory")
def get_panchayat_advisory(
    panchayat_id: str,
    timestamp: Optional[str] = Query(None),
    lead_time: int = Query(24)
):
    """Return gated crop advisories for a Gram Panchayat."""
    detail = service.get_panchayat_detail(
        panchayat_id=panchayat_id,
        timestamp=timestamp,
        lead_time=lead_time
    )
    return {
        "panchayat_id": detail["panchayat_id"],
        "timestamp": detail["timestamp"],
        "advisories": detail["advisories"],
        "freshness_status": detail["freshness"]["status"]
    }


@app.get("/api/v1/block-comparison")
def get_block_comparison(
    block_name: Optional[str] = Query(None, description="Block name (e.g., Anaimalai, Annur, Perur)"),
    timestamp: Optional[str] = Query(None),
    lead_time: int = Query(24)
):
    """Return coarse district forecast vs downscaled panchayat predictions for spatial variation comparison."""
    return service.get_block_comparison(
        block_name=block_name,
        timestamp=timestamp,
        lead_time=lead_time
    )


# ─── Phase 10 Live Weather Endpoints ──────────────────────────────────────────

@app.get("/api/live/weather")
def get_live_weather():
    """
    Return current real-time Coimbatore weather from Open-Meteo with provenance.
    Falls back to cached or historical replay if API is unavailable.
    IMPORTANT: Live data is a regional observation, not a validated panchayat downscale.
    """
    result = fetch_live_weather()
    live_data = result.get("data")
    prov = result.get("provenance")

    if live_data is None:
        return {
            "status": result["status"],
            "mode_label": "HISTORICAL REPLAY",
            "data": None,
            "provenance": prov,
            "error": result.get("error"),
            "disclaimer": "Live weather unavailable. Falling back to historical replay mode.",
        }

    is_valid, errors, validation_summary = validate_live_weather(live_data)
    freshness = get_freshness_status(live_data["data_age_seconds"])
    mode_label = get_mode_label(result["status"], freshness)

    return {
        "status": result["status"],
        "mode_label": mode_label,
        "cache_used": result.get("cache_used", False),
        "validation": validation_summary,
        "freshness": freshness,
        "provenance": prov,
        "data": live_data,
        "model_note": (
            "LIVE REGIONAL WEATHER — This is a direct Open-Meteo observation for Coimbatore. "
            "It is NOT output from the GramDrishti downscaling model. "
            "GramDrishti model validation is based on the historical test set (Jan–Jun 2024)."
        ),
        "error": result.get("error"),
    }


@app.get("/api/live/forecast")
def get_live_forecast(hours: int = Query(12, description="Number of hourly forecast steps to return (max 48)")):
    """Return hourly forecast for Coimbatore from Open-Meteo."""
    result = fetch_live_weather()
    live_data = result.get("data")

    if live_data is None:
        return {
            "status": result["status"],
            "mode_label": "HISTORICAL REPLAY",
            "forecast_hours": [],
            "error": result.get("error"),
        }

    hours = min(max(1, hours), 48)
    freshness = get_freshness_status(live_data["data_age_seconds"])
    mode_label = get_mode_label(result["status"], freshness)

    return {
        "status": result["status"],
        "mode_label": mode_label,
        "location": "Coimbatore, Tamil Nadu",
        "timezone": live_data.get("timezone"),
        "forecast_hours": live_data.get("forecast_hours", [])[:hours],
        "model_note": "LIVE FORECAST — Open-Meteo 48h ahead. Not GramDrishti model output.",
    }


@app.get("/api/live/status")
def get_live_status():
    """Return connectivity and freshness status of the live data layer."""
    result = fetch_live_weather()
    live_data = result.get("data")
    freshness = get_freshness_status(live_data["data_age_seconds"]) if live_data else "UNAVAILABLE"
    mode_label = get_mode_label(result["status"], freshness)

    return {
        "live_api_reachable": result["status"] == "live",
        "fetch_status": result["status"],
        "mode_label": mode_label,
        "freshness": freshness,
        "cache_used": result.get("cache_used", False),
        "data_age_seconds": live_data["data_age_seconds"] if live_data else None,
        "last_timestamp": live_data["timestamp"] if live_data else None,
        "error": result.get("error"),
    }


@app.get("/api/live/source")
def get_live_source():
    """Return data source metadata and attribution for the live weather layer."""
    return {
        "provider": "Open-Meteo",
        "type": "Public — No API key required",
        "base_url": "https://api.open-meteo.com/v1/forecast",
        "docs": "https://open-meteo.com/en/docs",
        "attribution": "Open-Meteo.com — CC BY 4.0",
        "location": {
            "name": "Coimbatore",
            "state": "Tamil Nadu",
            "country": "India",
            "latitude": 11.0168,
            "longitude": 76.9558,
        },
        "variables": [
            "temperature_2m (°C)", "relative_humidity_2m (%)",
            "apparent_temperature (°C)", "precipitation (mm)",
            "weather_code (WMO)", "surface_pressure (hPa)",
            "wind_speed_10m (km/h)", "wind_direction_10m (°)",
            "cloud_cover (%)",
        ],
        "forecast_variables": [
            "temperature_2m", "relative_humidity_2m",
            "precipitation_probability (%)", "precipitation (mm)",
            "weather_code (WMO)",
        ],
        "update_frequency": "Every 15 minutes (current), hourly forecast",
        "model_note": (
            "Live data is for regional Coimbatore weather only. "
            "GramDrishti panchayat downscaling is validated on historical test data. "
            "Live model inference is labeled 'LIVE REGIONAL WEATHER' throughout the application."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

