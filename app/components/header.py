"""
GramDrishti — Header & System Status Component
"""

import streamlit as st
from app.schemas import SystemStatusReport, FreshnessStatus
from app.formatting import get_badge_html, get_status_badge


def render_header(status: SystemStatusReport, selected_panchayat_name: str, valid_time: str, lead_time: int):
    """Renders the top branding header and system freshness banner."""
    st.markdown(
        """
        <div style="padding: 1.5rem 0 1rem 0; border-bottom: 2px solid #e2e8f0; margin-bottom: 1.5rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h1 style="margin: 0; color: #0f172a; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.02em;">
                        🌾 GramDrishti
                    </h1>
                    <p style="margin: 0.3rem 0 0 0; color: #475569; font-size: 1.05rem; font-weight: 500;">
                        AI-Assisted Hyperlocal Weather Intelligence for Gram Panchayats
                    </p>
                    <div style="margin-top: 0.5rem; display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                        <span style="background-color: #f1f5f9; color: #0f172a; padding: 3px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem; border: 1px solid #cbd5e1;">
                            📍 Pilot Region: Coimbatore District, Tamil Nadu
                        </span>
                        <span style="color: #64748b; font-size: 0.85rem;">
                            180 Gram Panchayats • 8 IMD Stations • 1-km Grid
                        </span>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sub-bar with selection metadata
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**Selected Panchayat:**<br><span style='color: #2563eb; font-size: 1.1rem; font-weight: 700;'>{selected_panchayat_name}</span>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"**Forecast Valid Time:**<br><span style='color: #0f172a; font-weight: 600;'>{valid_time}</span>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**Lead Time:**<br><span style='color: #0f172a; font-weight: 600;'>+{lead_time} Hours</span>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"**Data Freshness:**<br>{get_status_badge(status.freshness_status)}", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 1.25rem;'></div>", unsafe_allow_html=True)


def render_system_status_sidebar(status: SystemStatusReport):
    """Renders the system status widget in the sidebar."""
    st.sidebar.markdown("### 🛰️ System Status")

    def st_badge(available: bool) -> str:
        return get_badge_html("Available", "success") if available else get_badge_html("Not Available", "neutral")

    st.sidebar.markdown(f"**Forecast Data:** {st_badge(status.forecast_data_available)}", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Rainfall Model:** {st_badge(status.rainfall_model_available)}", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Uncertainty (UQ):** {st_badge(status.uncertainty_available)}", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Reliability Engine:** {st_badge(status.reliability_available)}", unsafe_allow_html=True)
    st.sidebar.markdown(f"**Advisory Engine:** {st_badge(status.advisory_engine_available)}", unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="font-size: 0.8rem; color: #64748b; line-height: 1.4;">
            <strong>Domain:</strong> Coimbatore District, TN<br>
            <strong>Resolution:</strong> 1 km × 1 km<br>
            <strong>Phase 8:</strong> Standalone UI Layer
        </div>
        """,
        unsafe_allow_html=True,
    )
