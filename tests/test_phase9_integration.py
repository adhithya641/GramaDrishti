"""
GramDrishti — Phase 9 Integration & End-to-End Demo Tests
===========================================================
Verifies artifact availability, panchayat selection, forecast retrieval,
quantiles monotonicity (P10 <= P50 <= P90), evidence-based reliability statuses,
fallback handling, NOT_EVALUABLE rainfall thresholds, advisory gating,
historical replay protection labelling, and complete end-to-end request consistency.
"""

import os
import pytest
from fastapi.testclient import TestClient
from src.dashboard.app import app
from src.dashboard.service import DashboardDataService
from src.dashboard.demo_validation import DemoDataValidator


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def service():
    return DashboardDataService()


# Test A — Artifact availability
def test_a_artifact_availability():
    validator = DemoDataValidator()
    is_valid, msgs = validator.validate_all()
    assert is_valid, f"Demo artifacts missing: {msgs}"


# Test B — Panchayat selection
def test_b_panchayat_selection(client):
    res = client.get("/panchayat/GP_33_12_0001/forecast")
    assert res.status_code == 200
    data = res.json()
    assert data["panchayat_id"] == "GP_33_12_0001"
    assert data["panchayat_name"] == "Anaimalai Panchayat 1"
    assert data["block_name"] == "Anaimalai"


# Test C — Forecast retrieval
def test_c_forecast_retrieval(client):
    res = client.get("/panchayat/GP_33_12_0001/forecast?timestamp=2024-05-01&lead_time=24")
    assert res.status_code == 200
    data = res.json()
    assert data["timestamp"] == "2024-05-01"
    assert data["lead_time"] == 24
    assert "temperature" in data["forecast"]
    assert "humidity" in data["forecast"]


# Test D — Downscaled output
def test_d_downscaled_output(client):
    res = client.get("/api/v1/block-comparison?block_name=Anaimalai&timestamp=2024-05-01&lead_time=24")
    assert res.status_code == 200
    data = res.json()
    assert "coarse_district_forecast" in data
    assert "downscaled_panchayats" in data
    assert len(data["downscaled_panchayats"]) > 0


# Test E — Uncertainty bounds (P10 <= P50 <= P90)
def test_e_uncertainty_bounds(client):
    res = client.get("/panchayat/GP_33_12_0001/forecast")
    assert res.status_code == 200
    uq = res.json()["uncertainty"]
    
    t10, t50, t90 = uq["temperature"]["p10"], uq["temperature"]["p50"], uq["temperature"]["p90"]
    assert t10 <= t50 <= t90

    h10, h50, h90 = uq["humidity"]["p10"], uq["humidity"]["p50"], uq["humidity"]["p90"]
    assert h10 <= h50 <= h90


# Test F — Reliability status
def test_f_reliability_status(client):
    res = client.get("/panchayat/GP_33_12_0001/reliability")
    assert res.status_code == 200
    rel = res.json()["reliability"]
    allowed_states = {"HIGH", "MEDIUM", "LOW", "NOT_EVALUABLE", "EXPIRED", "UNAVAILABLE"}
    assert rel["overall"] in allowed_states
    assert rel["temperature"] in allowed_states
    assert rel["humidity"] == "LOW"
    assert rel["rain_10mm"] == "NOT_EVALUABLE"
    assert rel["rain_25mm"] == "NOT_EVALUABLE"


# Test G — Fallback source
def test_g_fallback_source(client):
    res = client.get("/panchayat/GP_33_12_0001/reliability")
    assert res.status_code == 200
    fb = res.json()["fallback"]
    assert fb["humidity"]["source"] in ["BASELINE_B2", "BASELINE_B3", "COARSE_FORECAST", "PRIMARY_MODEL_LOW_RELIABILITY"]
    assert fb["rain_10mm"]["source"] == "NONE_NOT_EVALUABLE"
    assert fb["rain_25mm"]["source"] == "NONE_NOT_EVALUABLE"


# Test H — Rainfall handling
def test_h_rainfall_handling(client):
    res = client.get("/panchayat/GP_33_12_0001/forecast")
    assert res.status_code == 200
    fc = res.json()["forecast"]
    rel = res.json()["reliability"]
    assert fc["rain_1mm"] is not None
    assert fc["rain_10mm"] is None
    assert fc["rain_25mm"] is None
    assert rel["rain_10mm"] == "NOT_EVALUABLE"
    assert rel["rain_25mm"] == "NOT_EVALUABLE"


# Test I — Advisory gating
def test_i_advisory_gating(client):
    res = client.get("/panchayat/GP_33_12_0001/advisory")
    assert res.status_code == 200
    advs = res.json()["advisories"]
    assert advs["humidity"]["advisory_status"] == "CAUTIONARY"
    assert advs["rain_10mm"]["advisory_status"] == "BLOCKED"
    assert advs["rain_25mm"]["advisory_status"] == "BLOCKED"


# Test J — Historical replay protection labelling
def test_j_historical_replay_protection(client):
    res_status = client.get("/api/v1/system-status")
    assert res_status.status_code == 200
    assert res_status.json()["data_mode"] == "OFFLINE REPLAY"

    res_comp = client.get("/api/v1/block-comparison")
    assert res_comp.status_code == 200
    assert res_comp.json()["data_source_label"] == "Historical replay / model output"


# Test K — End-to-end request consistency
def test_k_end_to_end_consistency(client):
    res = client.get("/panchayat/GP_33_12_0001/forecast?timestamp=2024-05-01&lead_time=24")
    assert res.status_code == 200
    d = res.json()

    # Verify complete chain consistency
    assert d["panchayat_id"] == "GP_33_12_0001"
    assert "forecast" in d
    assert "uncertainty" in d
    assert "reliability" in d
    assert "fallback" in d
    assert "advisories" in d
    assert d["uncertainty"]["temperature"]["p10"] <= d["uncertainty"]["temperature"]["p50"] <= d["uncertainty"]["temperature"]["p90"]
    assert d["reliability"]["rain_10mm"] == "NOT_EVALUABLE"
    assert d["advisories"]["rain_10mm"]["advisory_status"] == "BLOCKED"
