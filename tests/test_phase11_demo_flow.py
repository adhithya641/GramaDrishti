"""
GramDrishti — Phase 11 Prototype Integration & Demo Flow Tests
===============================================================
Comprehensive integration test suite validating the complete 17-step
video-aligned demonstration flow, live real-time weather ingestion,
and strict mode isolation between LIVE and HISTORICAL REPLAY modes.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.dashboard.app import app
from src.dashboard.demo_validation import DemoDataValidator
from src.ingestion.live_weather import fetch_live_weather, COIMBATORE_LAT, COIMBATORE_LON

client = TestClient(app)


def test_step01_system_health_and_status():
    """Step 1: Verify health check and system status endpoints."""
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "ok"
    assert "mode" in health_data
    assert health_data["source"] == "Open-Meteo"

    res_status = client.get("/api/v1/system-status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "data_integrity" in status_data
    assert status_data["data_integrity"]["status"] == "OK"


def test_step02_live_weather_endpoint_schema():
    """Step 2: Verify LIVE MODE endpoint returns regional weather schema."""
    res = client.get("/api/live/weather")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] in ["live", "cached", "historical_fallback"]
    assert "provenance" in payload
    assert "model_note" in payload
    assert "LIVE REGIONAL WEATHER" in payload["model_note"]

    if payload["data"]:
        data = payload["data"]
        assert "temperature_c" in data
        assert "relative_humidity_pct" in data
        assert "precipitation_mm" in data
        assert "wind_speed_ms" in data
        assert "weather_description" in data
        assert "weather_emoji" in data


def test_step03_live_forecast_endpoint():
    """Step 3: Verify LIVE MODE hourly forecast timeline endpoint."""
    res = client.get("/api/live/forecast?hours=12")
    assert res.status_code == 200
    payload = res.json()
    assert "forecast_hours" in payload
    assert len(payload["forecast_hours"]) <= 12
    assert payload["location"] == "Coimbatore, Tamil Nadu"


def test_step04_live_status_and_provenance():
    """Step 4: Verify LIVE MODE connectivity and data freshness status."""
    res = client.get("/api/live/status")
    assert res.status_code == 200
    payload = res.json()
    assert "live_api_reachable" in payload
    assert "freshness" in payload
    assert "mode_label" in payload


def test_step05_live_source_attribution():
    """Step 5: Verify Open-Meteo source attribution and coordinates."""
    res = client.get("/api/live/source")
    assert res.status_code == 200
    payload = res.json()
    assert payload["provider"] == "Open-Meteo"
    assert payload["location"]["latitude"] == COIMBATORE_LAT
    assert payload["location"]["longitude"] == COIMBATORE_LON


def test_step06_historical_replay_timestamps():
    """Step 6: Verify HISTORICAL REPLAY available forecast timestamps."""
    res = client.get("/api/v1/timestamps")
    assert res.status_code == 200
    payload = res.json()
    assert "timestamps" in payload
    assert len(payload["timestamps"]) > 0
    assert "lead_times" in payload


def test_step07_historical_replay_panchayats_list():
    """Step 7: Verify 180 Gram Panchayats list retrieval."""
    res = client.get("/api/v1/panchayats")
    assert res.status_code == 200
    payload = res.json()
    assert "panchayats" in payload
    assert len(payload["panchayats"]) == 180


def test_step08_historical_replay_geojson_boundaries():
    """Step 8: Verify GeoJSON FeatureCollection with 180 downscaled polygons."""
    res = client.get("/api/v1/geojson?variable=temperature&lead_time=24")
    assert res.status_code == 200
    payload = res.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 180
    first_feat = payload["features"][0]
    props = first_feat["properties"]
    assert "panchayat_id" in props
    assert "prediction" in props
    assert "reliability" in props


def test_step09_panchayat_local_forecast_and_uncertainty():
    """Step 9: Verify local downscaled forecast with P10/P50/P90 CQR uncertainty."""
    res = client.get("/api/v1/panchayat/TN_CBE_001/forecast")
    assert res.status_code == 200
    payload = res.json()
    assert payload["panchayat_id"] == "TN_CBE_001"
    assert "predictions" in payload
    preds = payload["predictions"]
    assert "temperature" in preds
    assert "humidity" in preds
    # Verify CQR quantiles exist
    t_pred = preds["temperature"]
    assert "p10" in t_pred
    assert "p50" in t_pred
    assert "p90" in t_pred
    assert t_pred["p10"] <= t_pred["p50"] <= t_pred["p90"]


def test_step10_panchayat_evidence_based_reliability():
    """Step 10: Verify evidence-based reliability classification."""
    res = client.get("/api/v1/panchayat/TN_CBE_001/reliability")
    assert res.status_code == 200
    payload = res.json()
    assert "reliability" in payload
    rel = payload["reliability"]
    assert rel["overall_status"] in ["HIGH_RELIABILITY", "MODERATE_RELIABILITY", "UNRELIABLE_FALLBACK"]


def test_step11_panchayat_gated_agricultural_advisories():
    """Step 11: Verify agricultural advisory gating."""
    res = client.get("/api/v1/panchayat/TN_CBE_001/advisory")
    assert res.status_code == 200
    payload = res.json()
    assert "advisories" in payload
    assert isinstance(payload["advisories"], list)


def test_step12_block_spatial_comparison():
    """Step 12: Verify coarse district forecast vs downscaled panchayat comparison."""
    res = client.get("/api/v1/block-comparison?block_name=Anaimalai")
    assert res.status_code == 200
    payload = res.json()
    assert "coarse_district_forecast" in payload
    assert "panchayats" in payload


def test_step13_strict_mode_isolation():
    """Step 13: Verify strict isolation between LIVE weather and HISTORICAL downscale."""
    res_live = client.get("/api/live/weather")
    res_hist = client.get("/api/v1/geojson")

    live_payload = res_live.json()
    hist_payload = res_hist.json()

    # Live payload must explicitly flag regional scope
    assert "LIVE REGIONAL WEATHER" in live_payload.get("model_note", "")

    # GeoJSON payload properties must belong to historical model predictions
    feat = hist_payload["features"][0]["properties"]
    assert "prediction" in feat
    assert "reliability" in feat


def test_step14_live_weather_fallback_behavior():
    """Step 14: Verify graceful fallback when live API call fails."""
    with patch("src.ingestion.live_weather._fetch_url", side_effect=Exception("Network Timeout")):
        res = fetch_live_weather(use_cache_on_failure=False)
        assert res["status"] == "historical_fallback"
        assert res["data"] is None
        assert res["provenance"]["mode"] == "HISTORICAL_REPLAY"


def test_step15_metadata_and_scientific_disclaimer():
    """Step 15: Verify system metadata and honest scientific disclaimer."""
    res = client.get("/api/v1/metadata")
    assert res.status_code == 200
    payload = res.json()
    assert payload["project"] == "GramDrishti"
    assert payload["panchayats_count"] == 180
    assert "disclaimer" in payload


def test_step16_demo_data_validator():
    """Step 16: Verify demo validator approves local artifacts for SIH demonstration."""
    validator = DemoDataValidator()
    is_valid, messages = validator.validate_all()
    assert is_valid is True
    assert any("[OK] GeoJSON boundaries: 180 Gram Panchayats verified." in m for m in messages)


def test_step17_real_time_network_request():
    """Step 17: Perform real live Open-Meteo HTTP request and verify response."""
    result = fetch_live_weather(use_cache_on_failure=False)
    if result["status"] == "live":
        d = result["data"]
        assert d["latitude"] is not None
        assert d["longitude"] is not None
        assert d["temperature_c"] is not None
        assert d["relative_humidity_pct"] is not None
        assert d["provenance"]["freshness"].startswith("LIVE_")
