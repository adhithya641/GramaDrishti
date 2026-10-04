"""
GramDrishti — Phase 10A Live Data Integration Tests
====================================================
Tests for live weather ingestion, validation, caching,
fallback behavior, and mode labeling.

All tests use mocked API responses — no internet dependency.
"""

import json
import os
import time
import pytest
from unittest.mock import patch, MagicMock

from src.ingestion.live_weather import (
    _parse_response,
    _save_cache,
    _load_cache,
    fetch_live_weather,
    get_freshness_status,
    build_forecast_url,
    WMO_CODE_MAP,
    CACHE_FILE,
)
from src.ingestion.live_validator import (
    validate_temperature,
    validate_humidity,
    validate_precipitation,
    validate_wind_speed,
    validate_pressure,
    validate_timestamp,
    validate_live_weather,
    get_mode_label,
    _classify_freshness,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

MOCK_OPEN_METEO_RESPONSE = {
    "latitude": 11.001758,
    "longitude": 76.99468,
    "generationtime_ms": 0.54,
    "utc_offset_seconds": 19800,
    "timezone": "Asia/Kolkata",
    "timezone_abbreviation": "GMT+5:30",
    "elevation": 431.0,
    "current_units": {
        "time": "iso8601",
        "interval": "seconds",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°C",
        "precipitation": "mm",
        "weather_code": "wmo code",
        "surface_pressure": "hPa",
        "wind_speed_10m": "km/h",
        "wind_direction_10m": "°",
        "cloud_cover": "%",
    },
    "current": {
        "time": "2026-10-04T20:45",
        "interval": 900,
        "temperature_2m": 24.4,
        "relative_humidity_2m": 94,
        "apparent_temperature": 29.5,
        "precipitation": 0.00,
        "weather_code": 3,
        "surface_pressure": 966.9,
        "wind_speed_10m": 4.5,
        "wind_direction_10m": 203,
        "cloud_cover": 96,
    },
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°C",
        "relative_humidity_2m": "%",
        "precipitation_probability": "%",
        "precipitation": "mm",
        "weather_code": "wmo code",
    },
    "hourly": {
        "time": [
            "2026-10-04T00:00", "2026-10-04T01:00", "2026-10-04T02:00",
            "2026-10-04T03:00", "2026-10-04T04:00", "2026-10-04T05:00",
        ],
        "temperature_2m": [25.4, 25.1, 24.9, 24.7, 24.6, 24.8],
        "relative_humidity_2m": [83, 84, 85, 87, 87, 87],
        "precipitation_probability": [0, 0, 0, 1, 3, 4],
        "precipitation": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "weather_code": [3, 3, 3, 3, 3, 3],
    },
}


@pytest.fixture
def mock_response():
    return MOCK_OPEN_METEO_RESPONSE.copy()


@pytest.fixture
def parsed_data(mock_response):
    return _parse_response(mock_response, time.time())


# ─── Test 1: API Response Parsing ─────────────────────────────────────────────

def test_1_parse_temperature(parsed_data):
    """API response temperature parses correctly."""
    assert parsed_data["temperature_c"] == 24.4


def test_1_parse_humidity(parsed_data):
    """API response humidity parses correctly."""
    assert parsed_data["relative_humidity_pct"] == 94


def test_1_parse_weather_code_description(parsed_data):
    """WMO code 3 maps to 'Overcast'."""
    assert parsed_data["weather_description"] == "Overcast"
    assert parsed_data["weather_code"] == 3


def test_1_parse_forecast_hours(parsed_data):
    """Hourly forecast entries are parsed correctly."""
    assert len(parsed_data["forecast_hours"]) == 6
    assert parsed_data["forecast_hours"][0]["temperature_c"] == 25.4
    assert parsed_data["forecast_hours"][0]["precipitation_probability_pct"] == 0


# ─── Test 2: Unit Conversion ──────────────────────────────────────────────────

def test_2_wind_kmh_to_ms(mock_response):
    """Wind speed converts correctly from km/h to m/s."""
    mock_response["current"]["wind_speed_10m"] = 36.0  # 36 km/h = 10.0 m/s
    parsed = _parse_response(mock_response, time.time())
    assert abs(parsed["wind_speed_ms"] - 10.0) < 0.01
    assert parsed["wind_speed_kmh"] == 36.0


def test_2_wind_none_is_safe(mock_response):
    """Missing wind speed returns None cleanly."""
    mock_response["current"]["wind_speed_10m"] = None
    parsed = _parse_response(mock_response, time.time())
    assert parsed["wind_speed_ms"] is None


# ─── Test 3: Timestamp Normalization ─────────────────────────────────────────

def test_3_timestamp_present(parsed_data):
    """Parsed data includes a non-None timestamp."""
    assert parsed_data["timestamp"] is not None
    assert "2026" in parsed_data["timestamp"]


def test_3_timestamp_validation_valid():
    """Valid ISO timestamp passes validation."""
    errors = validate_timestamp("2026-10-04T20:45")
    assert len(errors) == 0


def test_3_timestamp_validation_none():
    """Missing timestamp raises an ERROR."""
    errors = validate_timestamp(None)
    assert any(e.severity == "ERROR" for e in errors)


def test_3_timestamp_validation_malformed():
    """Malformed timestamp raises an ERROR."""
    errors = validate_timestamp("not-a-date")
    assert any(e.severity == "ERROR" for e in errors)


# ─── Test 4: Humidity Validation ─────────────────────────────────────────────

def test_4_humidity_valid():
    assert len(validate_humidity(68.5)) == 0
    assert len(validate_humidity(0.0)) == 0
    assert len(validate_humidity(100.0)) == 0


def test_4_humidity_out_of_range():
    errors = validate_humidity(105.0)
    assert any(e.severity == "ERROR" for e in errors)


def test_4_humidity_negative():
    errors = validate_humidity(-1.0)
    assert any(e.severity == "ERROR" for e in errors)


def test_4_humidity_none_is_warning():
    errors = validate_humidity(None)
    assert any(e.severity == "WARNING" for e in errors)


# ─── Test 5: Rainfall Validation ─────────────────────────────────────────────

def test_5_precipitation_valid():
    assert len(validate_precipitation(0.0)) == 0
    assert len(validate_precipitation(15.3)) == 0


def test_5_precipitation_negative():
    errors = validate_precipitation(-0.1)
    assert any(e.severity == "ERROR" for e in errors)


def test_5_precipitation_none_allowed():
    """None precipitation is acceptable (field is optional)."""
    assert len(validate_precipitation(None)) == 0


# ─── Test 6: Stale Data Detection ────────────────────────────────────────────

def test_6_fresh():
    assert get_freshness_status(300) == "FRESH"


def test_6_aging():
    assert get_freshness_status(1800) == "AGING"


def test_6_stale():
    assert get_freshness_status(5400) == "STALE"


def test_6_expired():
    assert get_freshness_status(12000) == "EXPIRED"


def test_6_classify_freshness_boundary():
    assert _classify_freshness(900) == "FRESH"
    assert _classify_freshness(901) == "AGING"
    assert _classify_freshness(3601) == "STALE"
    assert _classify_freshness(10801) == "EXPIRED"


# ─── Test 7: API Failure Handling ────────────────────────────────────────────

def test_7_api_failure_returns_fallback(tmp_path):
    """When the API fails and no cache exists, status is historical_fallback."""
    # Temporarily clear cache
    with patch("src.ingestion.live_weather.CACHE_FILE", str(tmp_path / "empty.json")):
        with patch("src.ingestion.live_weather._fetch_url", side_effect=Exception("connection refused")):
            result = fetch_live_weather(use_cache_on_failure=True)
    assert result["status"] == "historical_fallback"
    assert result["data"] is None
    assert result["error"] is not None


def test_7_api_failure_no_crash():
    """API failure must not raise an exception."""
    with patch("src.ingestion.live_weather._fetch_url", side_effect=TimeoutError("timeout")):
        with patch("src.ingestion.live_weather._load_cache", return_value=None):
            result = fetch_live_weather(use_cache_on_failure=True)
    assert "status" in result


# ─── Test 8: Cache Fallback ───────────────────────────────────────────────────

def test_8_cache_fallback_used(tmp_path):
    """When API fails but cache exists, status is 'cached'."""
    cache_path = str(tmp_path / "live_weather.json")
    cache_payload = {
        "fetched_at": "2026-10-04T15:00:00+00:00",
        "fetched_at_epoch": time.time() - 300,  # 5 min ago
        "source": "open-meteo",
        "location": "Coimbatore, Tamil Nadu",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "data": MOCK_OPEN_METEO_RESPONSE,
    }
    with open(cache_path, "w") as f:
        json.dump(cache_payload, f)

    with patch("src.ingestion.live_weather.CACHE_FILE", cache_path):
        with patch("src.ingestion.live_weather._fetch_url", side_effect=Exception("offline")):
            result = fetch_live_weather(use_cache_on_failure=True)

    assert result["status"] == "cached"
    assert result["data"] is not None
    assert result["cache_used"] is True


def test_8_live_data_updates_cache(tmp_path):
    """Successful live fetch writes to cache."""
    cache_path = str(tmp_path / "live_weather.json")
    with patch("src.ingestion.live_weather.CACHE_FILE", cache_path):
        with patch("src.ingestion.live_weather._fetch_url", return_value=MOCK_OPEN_METEO_RESPONSE):
            with patch("src.ingestion.live_weather.CACHE_DIR", str(tmp_path)):
                result = fetch_live_weather()
    assert result["status"] == "live"
    assert os.path.exists(cache_path)


# ─── Test 9: Mode Switching ───────────────────────────────────────────────────

def test_9_mode_label_live():
    assert "LIVE" in get_mode_label("live", "FRESH")
    assert "LIVE" in get_mode_label("live", "AGING")


def test_9_mode_label_cached():
    label = get_mode_label("cached", "STALE")
    assert "CACHED" in label or "LIVE" in label


def test_9_mode_label_historical():
    label = get_mode_label("historical_fallback", "EXPIRED")
    assert "HISTORICAL" in label or "REPLAY" in label


def test_9_live_never_labeled_historical():
    """Live data must never be labeled as historical replay."""
    label = get_mode_label("live", "FRESH")
    assert "HISTORICAL" not in label
    assert "REPLAY" not in label


# ─── Test 10: No API Key Leakage ─────────────────────────────────────────────

def test_10_url_has_no_api_key():
    """Built URL must not contain any API key parameter."""
    url = build_forecast_url()
    assert "apikey" not in url.lower()
    assert "api_key" not in url.lower()
    assert "token" not in url.lower()
    assert "key=" not in url.lower()


def test_10_source_string_no_credentials(parsed_data):
    """Source field must not leak any credentials."""
    source = parsed_data.get("source", "")
    assert "apikey" not in source.lower()
    assert "key=" not in source


# ─── Test 11: Malformed Response Handling ────────────────────────────────────

def test_11_empty_current_block():
    """Parsing a response with empty current block returns None fields safely."""
    malformed = {
        "latitude": 11.0, "longitude": 77.0, "elevation": 431.0,
        "timezone": "Asia/Kolkata",
        "current": {},  # empty
        "hourly": {"time": [], "temperature_2m": [], "relative_humidity_2m": [],
                   "precipitation_probability": [], "precipitation": [], "weather_code": []},
    }
    parsed = _parse_response(malformed, time.time())
    assert parsed["temperature_c"] is None
    assert parsed["relative_humidity_pct"] is None
    assert parsed["weather_description"] == "Unknown"


def test_11_missing_hourly_block():
    """Parsing without hourly block does not raise."""
    malformed = {
        "latitude": 11.0, "longitude": 77.0, "elevation": 431.0,
        "timezone": "Asia/Kolkata",
        "current": MOCK_OPEN_METEO_RESPONSE["current"],
        "hourly": {},
    }
    parsed = _parse_response(malformed, time.time())
    assert parsed["forecast_hours"] == []


def test_11_unknown_weather_code():
    """Unknown WMO code maps to 'Unknown'."""
    assert WMO_CODE_MAP.get(9999, "Unknown") == "Unknown"


def test_11_full_validation_invalid_temp(parsed_data):
    """Validation catches out-of-range temperature."""
    bad_data = dict(parsed_data)
    bad_data["temperature_c"] = 999.0
    is_valid, errors, summary = validate_live_weather(bad_data)
    assert not is_valid
    assert summary["error_count"] > 0


# ─── Test 12: Phase 10B Provenance & Endpoint Tests ───────────────────────────

def test_12_provenance_structure(parsed_data):
    """Provenance object strictly includes mode, source, coords, timestamps, and freshness."""
    prov = parsed_data.get("provenance")
    assert prov is not None
    assert prov["mode"] in ("LIVE", "LIVE_CACHED", "HISTORICAL_REPLAY")
    assert prov["source"] == "Open-Meteo"
    assert abs(prov["latitude"] - 11.0168) < 0.05
    assert abs(prov["longitude"] - 76.9558) < 0.05
    assert "observed_at" in prov
    assert "fetched_at" in prov
    assert "data_age_seconds" in prov
    assert prov["freshness"].startswith("LIVE_")


def test_13_no_2024_dates_in_live_parsed_data(parsed_data):
    """Live parsed data contains current 2026 timestamp, not 2024 historical dates."""
    assert "2024" not in str(parsed_data["timestamp"])
    assert "2026" in str(parsed_data["timestamp"])


def test_14_fastapi_live_endpoints():
    """Test FastAPI /api/live/weather and /api/v1/metadata endpoints."""
    from fastapi.testclient import TestClient
    from src.dashboard.app import app

    client = TestClient(app)

    with patch("src.dashboard.app.fetch_live_weather") as mock_fetch:
        mock_fetch.return_value = {
            "status": "live",
            "data": _parse_response(MOCK_OPEN_METEO_RESPONSE, time.time()),
            "provenance": {
                "mode": "LIVE",
                "source": "Open-Meteo",
                "latitude": 11.0168,
                "longitude": 76.9558,
                "observed_at": "2026-10-04T20:45",
                "fetched_at": "2026-10-04T15:30:00+00:00",
                "data_age_seconds": 12.5,
                "freshness": "LIVE_FRESH",
            },
            "error": None,
            "cache_used": False,
        }

        # 1. Weather endpoint
        response = client.get("/api/live/weather")
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "live"
        assert res_json["provenance"]["mode"] == "LIVE"
        assert res_json["data"]["temperature_c"] == 24.4

        # 2. Metadata default mode
        meta_res = client.get("/api/v1/metadata")
        assert meta_res.status_code == 200
        meta_json = meta_res.json()
        assert meta_json["default_mode"] == "LIVE"
        assert meta_json["phase"] in ("10B", "10C")


# ─── Test 15: Phase 10C UI Mutual Exclusion & HTML State Integrity ───────────

def test_15_index_html_ui_mutual_exclusion():
    """Verify index.html contains isolated view containers, single mode switcher, and LIVE default."""
    html_path = os.path.join("src", "dashboard", "static", "index.html")
    assert os.path.exists(html_path)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Mutually exclusive containers exist
    assert 'id="view-live"' in html
    assert 'id="view-historical"' in html
    assert 'display: none;' in html  # Historical view hidden by default

    # 2. Default app mode is LIVE
    assert "let currentMode = 'LIVE';" in html or 'let currentMode = "LIVE";' in html

    # 3. Single mode switcher buttons
    assert 'id="btn-mode-live"' in html
    assert 'id="btn-mode-historical"' in html

    # 4. Header status badge isolation element
    assert 'id="header-status-badge"' in html

    # 5. Live view contains live weather elements
    assert 'id="card-temp"' in html
    assert 'id="card-humidity"' in html
    assert 'id="card-rain"' in html
    assert 'id="card-wind"' in html
    assert 'id="forecast-timeline"' in html
    assert 'LIVE REGIONAL WEATHER' in html


def test_16_live_weather_endpoint_no_2024_dates():
    """Live weather API response must contain current timestamp, not 2024 historical dates."""
    from fastapi.testclient import TestClient
    from src.dashboard.app import app

    client = TestClient(app)
    with patch("src.dashboard.app.fetch_live_weather") as mock_fetch:
        mock_fetch.return_value = {
            "status": "live",
            "data": _parse_response(MOCK_OPEN_METEO_RESPONSE, time.time()),
            "provenance": {
                "mode": "LIVE",
                "source": "Open-Meteo",
                "latitude": 11.0168,
                "longitude": 76.9558,
                "observed_at": "2026-10-04T20:45",
                "fetched_at": "2026-10-04T15:30:00+00:00",
                "data_age_seconds": 5.0,
                "freshness": "LIVE_FRESH",
            },
            "error": None,
            "cache_used": False,
        }
        res = client.get("/api/live/weather")
        assert res.status_code == 200
        payload = res.json()
        assert payload["status"] == "live"
        assert "2024" not in payload["data"]["timestamp"]
        assert "2026" in payload["data"]["timestamp"]
        assert payload["provenance"]["mode"] == "LIVE"


def test_17_historical_timestamps_endpoint_returns_2024_dates():
    """Historical timestamps endpoint returns 2024 dates for replay mode."""
    from fastapi.testclient import TestClient
    from src.dashboard.app import app

    client = TestClient(app)
    res = client.get("/api/v1/timestamps")
    assert res.status_code == 200
    ts_list = res.json().get("timestamps", [])
    assert len(ts_list) > 0
    assert any("2024" in ts for ts in ts_list)


def test_18_live_forecast_endpoint():
    """Live forecast endpoint returns hourly entries from Open-Meteo payload."""
    from fastapi.testclient import TestClient
    from src.dashboard.app import app

    client = TestClient(app)
    with patch("src.dashboard.app.fetch_live_weather") as mock_fetch:
        mock_fetch.return_value = {
            "status": "live",
            "data": _parse_response(MOCK_OPEN_METEO_RESPONSE, time.time()),
            "error": None,
        }
        res = client.get("/api/live/forecast?hours=12")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "live"
        assert len(data["forecast_hours"]) == 6


def test_19_live_status_endpoint():
    """Live status endpoint returns reachability and freshness status."""
    from fastapi.testclient import TestClient
    from src.dashboard.app import app

    client = TestClient(app)
    with patch("src.dashboard.app.fetch_live_weather") as mock_fetch:
        mock_fetch.return_value = {
            "status": "live",
            "data": _parse_response(MOCK_OPEN_METEO_RESPONSE, time.time()),
            "error": None,
        }
        res = client.get("/api/live/status")
        assert res.status_code == 200
        data = res.json()
        assert data["live_api_reachable"] is True
        assert data["fetch_status"] == "live"


def test_20_live_source_endpoint():
    """Live source endpoint returns Open-Meteo provider metadata and attribution."""
    from fastapi.testclient import TestClient
    from src.dashboard.app import app

    client = TestClient(app)
    res = client.get("/api/live/source")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "Open-Meteo"
    assert "CC BY 4.0" in data["attribution"]
    assert data["location"]["latitude"] == 11.0168


