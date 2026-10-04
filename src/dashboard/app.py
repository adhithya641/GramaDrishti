"""
GramDrishti — Phase 8 FastAPI Application Server
=================================================
REST API & Interactive Dashboard server for SIH demonstration.
Runs 100% offline using local data artifacts.
"""

import os
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.dashboard.service import DashboardDataService

app = FastAPI(
    title="GramDrishti API",
    description="Terrain-Aware Panchayat Weather Downscaling & Agro-Advisory API (SIH PS 26074)",
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


@app.get("/api/v1/system-status")
def get_system_status():
    """Return runtime system health and data status checks."""
    return service.get_system_status()


@app.get("/api/v1/metadata")
def get_metadata():
    """Return metadata summary and validation timestamp."""
    return {
        "project": "GramDrishti",
        "phase": 8,
        "pilot_region": "Coimbatore, Tamil Nadu",
        "panchayats_count": 180,
        "grid_resolution": "1 km",
        "data_mode": "OFFLINE REPLAY",
        "last_updated": "2026-09-30T10:39:52.003367+00:00",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
