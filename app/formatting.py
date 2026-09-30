"""
GramDrishti — UI Formatting & Presentation Utilities
=====================================================
Standardized text formatting, HTML badges, uncertainty visualizers, and cards.
"""

from typing import Optional, Union
import numpy as np


def format_temperature(val: Optional[float], decimals: int = 1) -> str:
    """Formats temperature value in Celsius."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:.{decimals}f} °C"


def format_humidity(val: Optional[float], decimals: int = 1) -> str:
    """Formats relative humidity percentage."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return f"{val:.{decimals}f} %"


def format_interval(p10: Optional[float], p90: Optional[float], unit: str = "", decimals: int = 1) -> str:
    """Formats uncertainty interval string P10 — P90."""
    if p10 is None or p90 is None or np.isnan(p10) or np.isnan(p90):
        return "Interval unavailable"
    unit_str = f" {unit}" if unit else ""
    return f"{p10:.{decimals}f} — {p90:.{decimals}f}{unit_str}"


def format_probability(val: Optional[float], is_evaluable: bool = True) -> str:
    """Formats probability in percent or returns Not evaluable."""
    if not is_evaluable or val is None or np.isnan(val):
        return "Not evaluable"
    pct = val * 100.0
    return f"{pct:.1f}%"


def generate_ascii_prob_bar(val: Optional[float], is_evaluable: bool = True, length: int = 20) -> str:
    """Generates a text-based progress bar for rainfall probability."""
    if not is_evaluable or val is None or np.isnan(val):
        return "Not evaluable"
    val = max(0.0, min(1.0, float(val)))
    filled = int(round(val * length))
    unfilled = length - filled
    return "█" * filled + "░" * unfilled + f" {val * 100.0:.1f}%"


def get_badge_html(text: str, badge_type: str = "info") -> str:
    """Generates an HTML badge for streamlit rendering."""
    colors = {
        "success": ("#dcfce7", "#15803d", "#86efac"),  # bg, text, border
        "warning": ("#fef9c3", "#a16207", "#fde047"),
        "danger": ("#fee2e2", "#b91c1c", "#fca5a5"),
        "info": ("#e0f2fe", "#0369a1", "#7dd3fc"),
        "neutral": ("#f1f5f9", "#475569", "#cbd5e1"),
        "high": ("#dcfce7", "#15803d", "#86efac"),
        "medium": ("#fef9c3", "#a16207", "#fde047"),
        "low": ("#fee2e2", "#b91c1c", "#fca5a5"),
        "not_evaluable": ("#f3e8ff", "#6b21a8", "#d8b4fe"),
    }
    bg, fg, border = colors.get(badge_type.lower(), colors["neutral"])
    return f'<span style="background-color: {bg}; color: {fg}; border: 1px solid {border}; padding: 3px 10px; border-radius: 9999px; font-weight: 600; font-size: 0.82rem; display: inline-block;">{text}</span>'


def get_reliability_badge(level: Optional[str]) -> str:
    """Returns styled badge for reliability levels."""
    if not level or level.upper() == "UNAVAILABLE":
        return get_badge_html("UNAVAILABLE", "neutral")
    lvl = level.upper()
    if lvl == "HIGH":
        return get_badge_html("HIGH", "high")
    elif lvl == "MEDIUM":
        return get_badge_html("MEDIUM", "medium")
    elif lvl == "LOW":
        return get_badge_html("LOW", "low")
    elif "NOT_EVALUABLE" in lvl or "DATA_LIMITED" in lvl:
        return get_badge_html("NOT EVALUABLE", "not_evaluable")
    return get_badge_html(level, "info")


def get_status_badge(status: str) -> str:
    """Returns styled badge for aggregation or freshness status."""
    st = status.upper()
    if st == "OK" or st == "FRESH":
        return get_badge_html(st, "success")
    elif st == "AGING" or st == "SUBGRID_RANGE_UNRESOLVED":
        return get_badge_html(st, "warning")
    elif st == "EXPIRED":
        return get_badge_html(st, "danger")
    return get_badge_html(st, "neutral")
