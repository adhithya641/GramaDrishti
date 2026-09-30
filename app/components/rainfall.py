"""
GramDrishti — Rainfall Forecast & Visualization Component
"""

import streamlit as st
from app.schemas import RainfallForecastData
from app.formatting import (
    format_probability,
    generate_ascii_prob_bar,
    get_badge_html,
    get_status_badge,
)


def render_rainfall_section(rain_fc: RainfallForecastData):
    """Renders rainfall probability cards for >=1mm, >=10mm, and >=25mm thresholds."""
    st.markdown("### 🌧️ Hyperlocal Rainfall Probability")

    if not rain_fc or not rain_fc.is_valid:
        st.error(f"⚠️ Data validation error — value withheld: {rain_fc.validation_error if rain_fc else 'Rainfall record not found'}")
        return

    # Check aggregation status
    if rain_fc.aggregation_status == "SUBGRID_RANGE_UNRESOLVED":
        st.warning(
            "⚠️ **Aggregation Status: SUBGRID_RANGE_UNRESOLVED** — "
            "This Panchayat contains edge or single-cell boundary geometry where subgrid spatial variance cannot be fully resolved. "
            "The aggregated probability is based on the available overlapping 1-km grid cell."
        )

    col1, col2, col3 = st.columns(3)

    # 1. Rain >= 1mm
    with col1:
        prob_1mm = rain_fc.rain_probability_1mm
        pct_1mm = (prob_1mm * 100.0) if prob_1mm is not None else 0.0
        ascii_bar = generate_ascii_prob_bar(prob_1mm, is_evaluable=True)

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%); border: 1px solid #bfdbfe; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #1e40af; font-size: 1.05rem;">Rainfall ≥ 1.0 mm</span>
                    <span>{get_badge_html("Calibrated", "success")}</span>
                </div>
                <div style="font-size: 2.3rem; font-weight: 800; color: #1d4ed8; margin: 0.25rem 0;">
                    {format_probability(prob_1mm, is_evaluable=True)}
                </div>
                <div style="font-family: monospace; font-size: 0.82rem; color: #1e40af; background-color: #dbeafe; padding: 6px 10px; border-radius: 6px; margin: 0.5rem 0;">
                    {ascii_bar}
                </div>
                <div style="font-size: 0.78rem; color: #475569; margin-top: 0.5rem;">
                    <strong>Spatial Spread (1-km):</strong> {rain_fc.rain_probability_1mm_p10 * 100.0 if rain_fc.rain_probability_1mm_p10 is not None else 0.0:.1f}% — {rain_fc.rain_probability_1mm_p90 * 100.0 if rain_fc.rain_probability_1mm_p90 is not None else 0.0:.1f}%<br>
                    <strong>Grid Cells:</strong> {rain_fc.grid_cell_count} cells aggregated
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 2. Rain >= 10mm (Data Limited)
    with col2:
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #faf5ff 0%, #ffffff 100%); border: 1px solid #e9d5ff; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #6b21a8; font-size: 1.05rem;">Rainfall ≥ 10.0 mm</span>
                    <span>{get_badge_html("Data-Limited", "warning")}</span>
                </div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #7e22ce; margin: 0.6rem 0;">
                    Not evaluable
                </div>
                <div style="background-color: #f3e8ff; border-left: 3px solid #a855f7; padding: 6px 10px; font-size: 0.78rem; color: #581c87; border-radius: 4px; margin-top: 0.4rem;">
                    Insufficient validated historical events in training and calibration sets.
                </div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.75rem;">
                    Scientific policy: Not evaluated to prevent uncalibrated risk estimates.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 3. Rain >= 25mm (Unobserved)
    with col3:
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #f8fafc 0%, #ffffff 100%); border: 1px solid #e2e8f0; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #334155; font-size: 1.05rem;">Rainfall ≥ 25.0 mm</span>
                    <span>{get_badge_html("Not Evaluable", "neutral")}</span>
                </div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #475569; margin: 0.6rem 0;">
                    Not evaluable
                </div>
                <div style="background-color: #f1f5f9; border-left: 3px solid #94a3b8; padding: 6px 10px; font-size: 0.78rem; color: #334155; border-radius: 4px; margin-top: 0.4rem;">
                    Unobserved extreme precipitation threshold in regional historical dataset.
                </div>
                <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.75rem;">
                    Scientific policy: Value withheld rather than fabricated as 0.0%.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
