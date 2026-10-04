"""
GramDrishti — Phase 10A Live Weather Ingestion
===============================================
Fetches real-time weather data for Coimbatore from Open-Meteo API.
No API key required. Free and open-source weather data.

Data source: Open-Meteo (https://open-meteo.com)
Provider: Open-Meteo — aggregates DWD, ECMWF, GFS, MeteoFrance
Coverage: Global, 1–11 km resolution
Update frequency: Every 15 minutes (analysis), hourly forecast
Attribution: Open-Meteo is open source under CC BY 4.0
"""

import json
import os
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Coimbatore centroid coordinates (EPSG:4326)
COIMBATORE_LAT = 11.0168
COIMBATORE_LON = 76.9558

# Open-Meteo endpoints — no API key required for non-commercial use
FORECAST_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Cache directory (relative to project root)
CACHE_DIR = "data/cache"
CACHE_FILE = os.path.join(CACHE_DIR, "live_weather.json")

# Freshness thresholds (seconds)
FRESH_THRESHOLD = 900      # 15 min
AGING_THRESHOLD = 3600     # 1 hour
STALE_THRESHOLD = 10800    # 3 hours

# WMO weather code descriptions
WMO_CODE_MAP = {
    0: "Clear Sky",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing Rime Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    77: "Snow Grains",
    80: "Slight Showers", 81: "Moderate Showers", 82: "Violent Showers",
    85: "Slight Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Slight Hail",
    99: "Thunderstorm w/ Heavy Hail",
}

WMO_ICON_MAP = {
    0: "sunny", 1: "mostly_sunny", 2: "partly_cloudy", 3: "cloudy",
    45: "foggy", 48: "foggy",
    51: "light_rain", 53: "light_rain", 55: "rain",
    61: "rain", 63: "rain", 65: "heavy_rain",
    71: "snow", 73: "snow", 75: "snow", 77: "snow",
    80: "showers", 81: "showers", 82: "heavy_showers",
    85: "snow_showers", 86: "snow_showers",
    95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm",
}

WMO_EMOJI_MAP = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️",
    61: "🌧️", 63: "🌧️", 65: "🌧️",
    71: "🌨️", 73: "🌨️", 75: "❄️", 77: "❄️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    85: "🌨️", 86: "❄️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}


def build_forecast_url(
    lat: float = COIMBATORE_LAT,
    lon: float = COIMBATORE_LON,
    forecast_days: int = 2
) -> str:
    """Build Open-Meteo API URL for Coimbatore current + hourly forecast."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation",
            "weather_code",
            "surface_pressure",
            "wind_speed_10m",
            "wind_direction_10m",
            "cloud_cover",
        ]),
        "hourly": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation_probability",
            "precipitation",
            "weather_code",
        ]),
        "forecast_days": forecast_days,
        "timezone": "Asia/Kolkata",
    }
    return f"{FORECAST_BASE_URL}?{urllib.parse.urlencode(params)}"


def _fetch_url(url: str, timeout: int = 10) -> dict:
    """Perform HTTP GET and return parsed JSON. Raises on error."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "GramDrishti/1.0 (https://github.com/adhithya641/GramaDrishti)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _save_cache(data: dict) -> None:
    """Persist fetched data to local cache file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fetched_at_epoch": time.time(),
        "source": "open-meteo",
        "location": "Coimbatore, Tamil Nadu",
        "latitude": COIMBATORE_LAT,
        "longitude": COIMBATORE_LON,
        "data": data,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _load_cache() -> Optional[dict]:
    """Load cached weather data if it exists."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _parse_response(raw: dict, fetched_at_epoch: float) -> dict:
    """
    Parse Open-Meteo API response into GramDrishti internal schema.
    Returns a clean, validated weather observation dict with provenance.
    """
    now_epoch = time.time()
    data_age = max(0.0, now_epoch - fetched_at_epoch)

    current = raw.get("current", {})
    hourly = raw.get("hourly", {})

    # Wind speed from km/h to m/s
    ws_kmh = current.get("wind_speed_10m")
    wind_ms = round(ws_kmh / 3.6, 2) if ws_kmh is not None else None

    weather_code = current.get("weather_code")

    # Extract hourly entries for forecast timeline
    h_times = hourly.get("time", [])
    h_temp = hourly.get("temperature_2m", [])
    h_rh = hourly.get("relative_humidity_2m", [])
    h_precip_prob = hourly.get("precipitation_probability", [])
    h_precip = hourly.get("precipitation", [])
    h_wcode = hourly.get("weather_code", [])

    forecast_hours: List[Dict[str, Any]] = []
    for i, t in enumerate(h_times[:48]):
        wc = h_wcode[i] if i < len(h_wcode) else None
        forecast_hours.append({
            "time": t,
            "temperature_c": h_temp[i] if i < len(h_temp) else None,
            "relative_humidity_pct": h_rh[i] if i < len(h_rh) else None,
            "precipitation_probability_pct": h_precip_prob[i] if i < len(h_precip_prob) else None,
            "precipitation_mm": h_precip[i] if i < len(h_precip) else None,
            "weather_code": wc,
            "weather_description": WMO_CODE_MAP.get(wc, "Unknown"),
            "weather_icon": WMO_ICON_MAP.get(wc, "partly_cloudy"),
            "weather_emoji": WMO_EMOJI_MAP.get(wc, "🌡️"),
        })

    freshness_status = get_freshness_status(data_age)
    fetched_at_utc = datetime.fromtimestamp(fetched_at_epoch, tz=timezone.utc).isoformat()

    provenance = {
        "mode": "LIVE",
        "source": "Open-Meteo",
        "latitude": raw.get("latitude", COIMBATORE_LAT),
        "longitude": raw.get("longitude", COIMBATORE_LON),
        "observed_at": current.get("time"),
        "fetched_at": fetched_at_utc,
        "data_age_seconds": round(data_age, 1),
        "freshness": f"LIVE_{freshness_status}",
    }

    return {
        "timestamp": current.get("time"),
        "latitude": raw.get("latitude"),
        "longitude": raw.get("longitude"),
        "elevation_m": raw.get("elevation"),
        "timezone": raw.get("timezone"),
        "temperature_c": current.get("temperature_2m"),
        "apparent_temperature_c": current.get("apparent_temperature"),
        "relative_humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "weather_code": weather_code,
        "weather_description": WMO_CODE_MAP.get(weather_code, "Unknown"),
        "weather_icon": WMO_ICON_MAP.get(weather_code, "partly_cloudy"),
        "weather_emoji": WMO_EMOJI_MAP.get(weather_code, "🌡️"),
        "surface_pressure_hpa": current.get("surface_pressure"),
        "wind_speed_ms": wind_ms,
        "wind_speed_kmh": ws_kmh,
        "wind_direction_deg": current.get("wind_direction_10m"),
        "cloud_cover_pct": current.get("cloud_cover"),
        "source": "Open-Meteo (ECMWF IFS / DWD ICON / GFS composite)",
        "source_url": "https://open-meteo.com",
        "data_age_seconds": round(data_age, 1),
        "fetched_at_epoch": fetched_at_epoch,
        "forecast_hours": forecast_hours,
        "provenance": provenance,
    }


def fetch_live_weather(use_cache_on_failure: bool = True) -> Dict[str, Any]:
    """
    Fetch current Coimbatore weather from Open-Meteo.

    Returns a dict with:
        status: "live" | "cached" | "historical_fallback"
        data:   parsed weather observation or None
        provenance: dict with mode, source, timestamps, data age
        error:  error message if applicable
        cache_used: bool
    """
    url = build_forecast_url()
    fetch_epoch = time.time()

    try:
        raw = _fetch_url(url)
        _save_cache(raw)
        parsed = _parse_response(raw, fetch_epoch)
        return {
            "status": "live",
            "data": parsed,
            "provenance": parsed["provenance"],
            "error": None,
            "cache_used": False,
        }
    except Exception as exc:
        error_msg = str(exc)

        if use_cache_on_failure:
            cached = _load_cache()
            if cached:
                cache_age = time.time() - cached.get("fetched_at_epoch", 0)
                parsed = _parse_response(cached["data"], cached.get("fetched_at_epoch", fetch_epoch))
                parsed["data_age_seconds"] = round(cache_age, 1)
                prov = parsed["provenance"]
                prov["mode"] = "LIVE_CACHED"
                prov["data_age_seconds"] = round(cache_age, 1)
                prov["freshness"] = f"LIVE_{get_freshness_status(cache_age)}"
                return {
                    "status": "cached",
                    "data": parsed,
                    "provenance": prov,
                    "error": error_msg,
                    "cache_used": True,
                    "cache_age_seconds": round(cache_age, 1),
                }

        fallback_prov = {
            "mode": "HISTORICAL_REPLAY",
            "source": "GramDrishti Historical Validation",
            "latitude": COIMBATORE_LAT,
            "longitude": COIMBATORE_LON,
            "observed_at": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data_age_seconds": None,
            "freshness": "EXPIRED",
        }
        return {
            "status": "historical_fallback",
            "data": None,
            "provenance": fallback_prov,
            "error": error_msg,
            "cache_used": False,
        }


def get_freshness_status(data_age_seconds: float) -> str:
    """Classify data freshness per Phase 7 philosophy."""
    if data_age_seconds <= FRESH_THRESHOLD:
        return "FRESH"
    elif data_age_seconds <= AGING_THRESHOLD:
        return "AGING"
    elif data_age_seconds <= STALE_THRESHOLD:
        return "STALE"
    return "EXPIRED"


if __name__ == "__main__":
    result = fetch_live_weather()
    print(f"Status: {result['status']}")
    if result["data"]:
        d = result["data"]
        print(f"Coimbatore: {d['temperature_c']}C, {d['relative_humidity_pct']}% RH")
        print(f"Condition: {d['weather_description']}")
        print(f"Data age: {d['data_age_seconds']}s ({get_freshness_status(d['data_age_seconds'])})")
        prov = result["provenance"]
        print(f"Provenance Mode: {prov['mode']}, Source: {prov['source']}, Observed: {prov['observed_at']}")
