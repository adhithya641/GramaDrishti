"""
GramDrishti — Main Streamlit Application
=========================================
SIH PS 26074: AI-Assisted Hyperlocal Weather Intelligence for Gram Panchayats
Phase 8: Standalone Application Layer (Read-Only)
"""

import streamlit as st
import pandas as pd
import numpy as np

from app.data_loader import DataLoader
from app.services import ForecastService
from app.schemas import SystemStatusReport, FreshnessStatus, AggregationStatus
from app.formatting import (
    format_temperature,
    format_humidity,
    format_probability,
    format_interval,
    get_badge_html,
    get_reliability_badge,
    get_status_badge,
)
from app.components.header import render_header, render_system_status_sidebar
from app.components.forecast_cards import render_forecast_cards
from app.components.rainfall import render_rainfall_section
from app.components.uncertainty import render_uncertainty_section
from app.components.advisory import render_advisory_section
from app.components.reliability import render_reliability_section
from app.components.map_view import render_map_view


# Streamlit Page Setup
st.set_page_config(
    page_title="GramDrishti — Hyperlocal Weather Intelligence",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }
    .stMetric {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 0.75rem 1rem;
        border-radius: 8px;
    }
    div[data-testid="stSidebarNav"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_service() -> ForecastService:
    loader = DataLoader()
    return ForecastService(loader)


def main():
    service = get_service()
    loader = service.loader
    status = loader.get_system_status()

    # Load dynamic Panchayats list
    panchayats = service.get_all_panchayats()
    if not panchayats:
        st.error("No Panchayat metadata found in project artifacts.")
        return

    # -------------------------------------------------------------
    # Sidebar Navigation & Controls
    # -------------------------------------------------------------
    st.sidebar.markdown(
        """
        <div style="text-align: center; padding: 0.5rem 0 1rem 0;">
            <h2 style="margin: 0; color: #1e3a8a; font-weight: 800;">🌾 GramDrishti</h2>
            <div style="font-size: 0.82rem; color: #64748b; font-weight: 500;">SIH PS 26074 • Phase 8 App</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page = st.sidebar.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "🌡️ Temperature & Humidity",
            "🌧️ Rainfall Intelligence",
            "🗺️ District Map View",
            "📈 Model Performance",
            "🛡️ Forecast Reliability",
            "🌾 Crop Advisory",
            "ℹ️ About & Scientific Policy",
        ],
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📍 Location & Forecast Settings")

    # Panchayat Selector (Dynamic, not hardcoded)
    panchayat_options = {
        f"{p.panchayat_name} ({p.block_name} Block)": p.panchayat_id for p in panchayats
    }
    selected_label = st.sidebar.selectbox(
        "Select Gram Panchayat",
        options=list(panchayat_options.keys()),
        index=0,
        help="Dynamic list of all 180 Gram Panchayats in Coimbatore District",
    )
    selected_panchayat_id = panchayat_options[selected_label]
    selected_panchayat = service.get_panchayat_by_id(selected_panchayat_id)

    # Lead Time Selector
    lead_time_options = service.get_available_lead_times()
    selected_lead_time = st.sidebar.select_slider(
        "Forecast Lead Time",
        options=lead_time_options,
        value=24,
        format_func=lambda x: f"+{x} Hours",
        help="Select forecast horizon (24, 48, or 72 hours)",
    )

    # Date Selector
    available_dates = service.get_available_dates()
    default_date_idx = len(available_dates) - 1 if available_dates else 0
    selected_date = st.sidebar.selectbox(
        "Forecast Date",
        options=available_dates,
        index=default_date_idx,
        help="Available forecast valid observation dates",
    )

    st.sidebar.markdown("---")
    render_system_status_sidebar(status)

    # -------------------------------------------------------------
    # Fetch View Data
    # -------------------------------------------------------------
    view_data = service.get_panchayat_view_data(
        panchayat_id=selected_panchayat_id,
        timestamp=selected_date,
        lead_time=selected_lead_time,
    )

    panchayat = view_data["panchayat"]
    weather_fc = view_data["weather_forecast"]
    rain_fc = view_data["rainfall_forecast"]

    # Render Header
    valid_time_str = f"{selected_date} (+{selected_lead_time}h)"
    render_header(
        status=status,
        selected_panchayat_name=f"{panchayat.panchayat_name} ({panchayat.block_name})",
        valid_time=valid_time_str,
        lead_time=selected_lead_time,
    )

    # -------------------------------------------------------------
    # Page Content Rendering
    # -------------------------------------------------------------
    if page == "📊 Dashboard":
        # Panchayat Summary Bar
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Panchayat Code", panchayat.panchayat_id)
        with col2:
            st.metric("Block / Taluk", panchayat.block_name)
        with col3:
            st.metric("Mean Elevation", f"{panchayat.elevation_mean:.0f} m" if panchayat.elevation_mean else "N/A")
        with col4:
            st.metric("1-km Grid Cells", f"{panchayat.grid_cell_count} cells")

        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

        # Main Weather Cards
        if weather_fc:
            render_forecast_cards(weather_fc, panchayat)
        else:
            st.warning("Weather forecast data currently unavailable for selected station.")

        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

        # Rainfall Cards
        if rain_fc:
            render_rainfall_section(rain_fc)
        else:
            st.warning("Rainfall prediction currently unavailable for this Panchayat.")

        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)

        # Uncertainty Preview
        if weather_fc:
            render_uncertainty_section(weather_fc)

    elif page == "🌡️ Temperature & Humidity":
        st.markdown("### 🌡️ Detailed Weather Predictions & Uncertainty Bands")
        if weather_fc:
            render_forecast_cards(weather_fc, panchayat)
            render_uncertainty_section(weather_fc)

            st.markdown("#### 🔬 Baseline vs ML Model Comparison")
            col_t, col_h = st.columns(2)
            with col_t:
                fig_t = ForecastService.create_baseline_comparison_chart(weather_fc, "temperature")
                if fig_t:
                    st.plotly_chart(fig_t, use_container_width=True)
            with col_h:
                fig_h = ForecastService.create_baseline_comparison_chart(weather_fc, "humidity")
                if fig_h:
                    st.plotly_chart(fig_h, use_container_width=True)

            st.markdown(
                """
                <div style="font-size: 0.85rem; color: #475569; background-color: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <strong>Model Progression Hierarchy:</strong><br>
                    • <strong>B0 (Raw NWP):</strong> Direct grid forecast without local downscaling.<br>
                    • <strong>B1 (Lapse Rate):</strong> Standard adiabatic lapse rate elevation adjustment (-6.5°C/km).<br>
                    • <strong>B2 (Geospatial Linear):</strong> Multi-feature terrain & landcover linear interpolation.<br>
                    • <strong>B3 (Quantile Mapping):</strong> Empirical distribution matching.<br>
                    • <strong>ML Residual Model:</strong> Gradient-boosted decision trees (LightGBM) trained on spatial residuals.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Weather forecast data unavailable.")

    elif page == "🌧️ Rainfall Intelligence":
        if rain_fc:
            render_rainfall_section(rain_fc)

            st.markdown("#### 📈 Multi-Lead Time Rainfall Evolution (May–June 2024)")
            fig_rain = ForecastService.create_rainfall_timeline_chart(selected_panchayat_id, loader)
            if fig_rain:
                st.plotly_chart(fig_rain, use_container_width=True)
            else:
                st.info("Timeline data unavailable for this Panchayat.")

            st.markdown(
                """
                <div style="font-size: 0.85rem; color: #475569; background-color: #f8fafc; padding: 1rem; border-radius: 8px; border: 1px solid #e2e8f0; margin-top: 1rem;">
                    <strong>Rainfall Evaluation & Calibration Policy:</strong><br>
                    • <strong>1.0 mm Threshold:</strong> Calibrated with Isotonic Regression on historical calibration split. Provides trustworthy probabilities of light-to-moderate rain events.<br>
                    • <strong>10.0 mm Threshold:</strong> Data-Limited (0 training events in dry season Q1). Preserved as un-evaluated.<br>
                    • <strong>25.0 mm Threshold:</strong> Unobserved in Coimbatore historical station record. Strictly labeled as Not Evaluable to prevent fabricated low risk estimates.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Rainfall data unavailable.")

    elif page == "🗺️ District Map View":
        render_map_view(
            loader=loader,
            selected_panchayat_id=selected_panchayat_id,
            timestamp=selected_date,
            lead_time=selected_lead_time,
        )

    elif page == "📈 Model Performance":
        st.markdown("### 📈 Scientific Model Performance & Audit Summaries")
        metrics = loader.load_model_performance()

        tab1, tab2, tab3 = st.tabs(["Phase 4 Weather Models", "Phase 5 Uncertainty (UQ)", "Phase 6 Rainfall Baselines"])

        with tab1:
            st.markdown("#### Station-Level MAE / RMSE Comparison")
            if "station_performance" in metrics:
                st.dataframe(metrics["station_performance"], use_container_width=True)
            if "feature_importance" in metrics:
                st.markdown("#### Top Predictive Features (LightGBM)")
                st.dataframe(metrics["feature_importance"].head(10), use_container_width=True)

        with tab2:
            st.markdown("#### Conformal Quantile Regression Audit")
            if "uncertainty_validation" in metrics:
                val_uq = metrics["uncertainty_validation"]
                cov = val_uq.get("coverage", {})
                st.json(cov)
                st.markdown(
                    """
                    **Key Finding:** Temperature UQ achieves 87.7% empirical test coverage against 80% nominal target.
                    Humidity UQ exhibits 20.15% test coverage due to summer distribution shift (dry season training vs wet pre-monsoon test).
                    """
                )

        with tab3:
            st.markdown("#### Rainfall Model Brier Scores & Baseline Comparison")
            if "rainfall_metrics" in metrics:
                st.dataframe(metrics["rainfall_metrics"], use_container_width=True)

    elif page == "🛡️ Forecast Reliability":
        render_reliability_section(view_data["phase7_reliability"])

    elif page == "🌾 Crop Advisory":
        render_advisory_section(view_data["phase7_advisory"])

    elif page == "ℹ️ About & Scientific Policy":
        st.markdown("### ℹ️ About GramDrishti & Scientific Safety Framework")
        st.markdown(
            """
            **GramDrishti** is an AI-assisted hyperlocal weather intelligence system developed for **Smart India Hackathon (SIH) PS 26074**.

            ---

            ### 📍 Pilot Scope & Constraints
            1. **Pilot Region:** Strictly **Coimbatore District, Tamil Nadu** (180 Gram Panchayats, 8 IMD Observation Stations).
            2. **No Nationwide Claims:** The models and calibrations are localized to the Western Ghats / Coimbatore topographical microclimate.
            3. **Resolution:** 1-km × 1-km spatial grid downscaling with digital elevation and landcover feature enrichment.

            ---

            ### 🛡️ Scientific Safety & Truths
            - **No Fabricated Zeros:** Unobserved precipitation thresholds (≥10mm, ≥25mm) remain explicitly marked as `NOT_EVALUABLE` rather than falsely reported as 0% probability.
            - **Honest Uncertainty:** Humidity uncertainty limitations are transparently communicated with reason codes.
            - **Read-Only Application Layer:** Phase 8 does not alter or recompute any Phase 1–7 ML metrics, conformal bounds, or predictions.

            ---

            ### 🛠️ Architecture & Start Command
            ```bash
            # To run locally:
            streamlit run app/main.py
            ```
            """
        )

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; font-size: 0.8rem; color: #94a3b8; padding-top: 0.5rem;">
            GramDrishti • SIH PS 26074 • Standalone Application Layer (Phase 8) • Coimbatore District Pilot
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
