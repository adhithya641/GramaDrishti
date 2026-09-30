"""
GramDrishti — Uncertainty Quantification (UQ) Component
"""

import streamlit as st
from app.schemas import WeatherForecastData
from app.services import ForecastService
from app.formatting import format_temperature, format_humidity, format_interval


def render_uncertainty_section(weather_fc: WeatherForecastData):
    """Renders visual uncertainty representation and conformal intervals."""
    st.markdown("### 📊 Uncertainty Quantification (CQR Intervals)")

    if not weather_fc or not weather_fc.is_valid:
        st.info("Uncertainty intervals are not available for this record.")
        return

    st.markdown(
        """
        <div style="font-size: 0.9rem; color: #475569; margin-bottom: 1rem;">
            GramDrishti uses <strong>Conformalized Quantile Regression (CQR)</strong> to provide mathematically guaranteed 80% prediction intervals (P10–P90) rather than point estimates.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🌡️ Temperature Uncertainty Band")
        if weather_fc.q10_temperature is not None and weather_fc.q90_temperature is not None:
            # Render ASCII representation
            p10_str = format_temperature(weather_fc.q10_temperature)
            p50_str = format_temperature(weather_fc.q50_temperature)
            p90_str = format_temperature(weather_fc.q90_temperature)
            st.markdown(
                f"""
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px; font-family: monospace; text-align: center;">
                    <div style="font-weight: bold; color: #1e293b; font-size: 1.1rem; margin-bottom: 0.5rem;">
                        P10 ───────── P50 ───────── P90
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: #475569;">
                        <span>{p10_str}</span>
                        <span style="font-weight: bold; color: #c2410c;">{p50_str}</span>
                        <span>{p90_str}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Interactive Chart
            fig_t = ForecastService.create_uncertainty_gauge(
                val=weather_fc.ml_temperature,
                p10=weather_fc.q10_temperature,
                p50=weather_fc.q50_temperature,
                p90=weather_fc.q90_temperature,
                title="Temperature Conformal Band (°C)",
                unit="°C",
                color="#f97316",
            )
            if fig_t:
                st.plotly_chart(fig_t, use_container_width=True)
        else:
            st.info("Temperature quantile data unavailable.")

    with col2:
        st.markdown("#### 💧 Relative Humidity Uncertainty Band")
        if weather_fc.q10_humidity is not None and weather_fc.q90_humidity is not None:
            p10_str = format_humidity(weather_fc.q10_humidity)
            p50_str = format_humidity(weather_fc.q50_humidity)
            p90_str = format_humidity(weather_fc.q90_humidity)
            st.markdown(
                f"""
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 1rem; border-radius: 8px; font-family: monospace; text-align: center;">
                    <div style="font-weight: bold; color: #1e293b; font-size: 1.1rem; margin-bottom: 0.5rem;">
                        P10 ───────── P50 ───────── P90
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; color: #475569;">
                        <span>{p10_str}</span>
                        <span style="font-weight: bold; color: #15803d;">{p50_str}</span>
                        <span>{p90_str}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            # Interactive Chart
            fig_h = ForecastService.create_uncertainty_gauge(
                val=weather_fc.ml_humidity,
                p10=weather_fc.q10_humidity,
                p50=weather_fc.q50_humidity,
                p90=weather_fc.q90_humidity,
                title="Humidity Conformal Band (%)",
                unit="%",
                color="#10b981",
            )
            if fig_h:
                st.plotly_chart(fig_h, use_container_width=True)
        else:
            st.info("Humidity quantile data unavailable.")
