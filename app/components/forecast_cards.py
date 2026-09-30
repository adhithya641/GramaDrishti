"""
GramDrishti — Weather Forecast Cards Component
"""

import streamlit as st
from app.schemas import WeatherForecastData, PanchayatInfo
from app.formatting import (
    format_temperature,
    format_humidity,
    format_interval,
    get_badge_html,
    get_reliability_badge,
)


def render_forecast_cards(
    weather_fc: WeatherForecastData,
    panchayat: PanchayatInfo,
    show_uncertainty_inline: bool = True
):
    """Renders temperature and humidity forecast cards with uncertainty intervals."""
    if not weather_fc or not weather_fc.is_valid:
        st.error(f"⚠️ Data validation error — value withheld: {weather_fc.validation_error if weather_fc else 'Forecast record not available'}")
        return

    col1, col2 = st.columns(2)

    with col1:
        # Temperature Card
        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #fff7ed 0%, #ffffff 100%); border: 1px solid #fed7aa; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-weight: 700; color: #9a3412; font-size: 1.1rem;">🌡️ Temperature Forecast</span>
                    <span>{get_reliability_badge(weather_fc.temperature_reliability)}</span>
                </div>
                <div style="font-size: 2.5rem; font-weight: 800; color: #c2410c; margin: 0.25rem 0;">
                    {format_temperature(weather_fc.ml_temperature)}
                </div>
                <div style="background-color: #ffedd5; padding: 0.6rem 0.8rem; border-radius: 8px; margin-top: 0.75rem; border: 1px solid #fdba74;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #7c2d12;">
                        <span>P10: {format_temperature(weather_fc.q10_temperature)}</span>
                        <span>P50: {format_temperature(weather_fc.q50_temperature)}</span>
                        <span>P90: {format_temperature(weather_fc.q90_temperature)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #9a3412; margin-top: 0.2rem;">
                        <span>80% Conformal Range: {format_interval(weather_fc.q10_temperature, weather_fc.q90_temperature, '°C')}</span>
                        <span>Width: ±{weather_fc.temp_interval_width / 2.0 if weather_fc.temp_interval_width else 0.0:.1f}°C</span>
                    </div>
                </div>
                <div style="font-size: 0.78rem; color: #64748b; margin-top: 0.6rem;">
                    Source: Residual ML model calibrated on IMD observation network
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        # Humidity Card
        hum_reason = ""
        if weather_fc.humidity_reliability and weather_fc.humidity_reliability.upper() == "LOW":
            hum_reason = """
            <div style="background-color: #fee2e2; border-left: 3px solid #ef4444; padding: 4px 8px; font-size: 0.75rem; color: #991b1b; margin-top: 0.5rem; border-radius: 2px;">
                <strong>Notice:</strong> Temporal distribution shift detected in summer test period.
            </div>
            """

        st.markdown(
            f"""
            <div style="background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 100%); border: 1px solid #bbf7d0; border-radius: 12px; padding: 1.25rem; box-shadow: 0 2px 4px rgba(0,0,0,0.03);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-weight: 700; color: #166534; font-size: 1.1rem;">💧 Relative Humidity</span>
                    <span>{get_reliability_badge(weather_fc.humidity_reliability)}</span>
                </div>
                <div style="font-size: 2.5rem; font-weight: 800; color: #15803d; margin: 0.25rem 0;">
                    {format_humidity(weather_fc.ml_humidity)}
                </div>
                <div style="background-color: #dcfce7; padding: 0.6rem 0.8rem; border-radius: 8px; margin-top: 0.75rem; border: 1px solid #86efac;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.9rem; font-weight: 600; color: #14532d;">
                        <span>P10: {format_humidity(weather_fc.q10_humidity)}</span>
                        <span>P50: {format_humidity(weather_fc.q50_humidity)}</span>
                        <span>P90: {format_humidity(weather_fc.q90_humidity)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #166534; margin-top: 0.2rem;">
                        <span>80% Conformal Range: {format_interval(weather_fc.q10_humidity, weather_fc.q90_humidity, '%')}</span>
                        <span>Width: ±{weather_fc.hum_interval_width / 2.0 if weather_fc.hum_interval_width else 0.0:.1f}%</span>
                    </div>
                </div>
                {hum_reason}
                <div style="font-size: 0.78rem; color: #64748b; margin-top: 0.6rem;">
                    Bounded quantile output with CQR empirical calibration
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
