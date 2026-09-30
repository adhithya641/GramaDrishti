"""
GramDrishti — District Map View Component
"""

from typing import Optional, List, Dict, Any
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from app.schemas import PanchayatInfo
from app.data_loader import DataLoader


def render_map_view(
    loader: DataLoader,
    selected_panchayat_id: str,
    timestamp: Optional[str] = None,
    lead_time: int = 24
):
    """Renders interactive Coimbatore district map with panchayat boundaries and stations."""
    st.markdown("### 🗺️ Coimbatore District Spatial Map (180 Gram Panchayats)")

    geojson_data = loader.load_geojson()
    if not geojson_data:
        st.info("ℹ️ Spatial boundary data is not available in this deployment.")
        return

    # Load rainfall predictions for current date/lead_time to colorize map
    df_pr = loader.load_panchayat_rainfall_df()
    panchayats = loader.load_panchayats()
    stations = loader.load_stations_metadata()

    map_df_rows = []
    for p in panchayats:
        prob = 0.0
        status = "OK"
        if not df_pr.empty:
            sub = df_pr[df_pr["panchayat_id"] == p.panchayat_id]
            if timestamp:
                sub = sub[sub["timestamp"] == timestamp]
            if lead_time:
                sub = sub[sub["lead_time"] == lead_time]
            if not sub.empty:
                prob = sub.iloc[-1].get("rain_probability_1mm", 0.0) * 100.0
                status = sub.iloc[-1].get("aggregation_status", "OK")

        map_df_rows.append({
            "panchayat_id": p.panchayat_id,
            "panchayat_name": p.panchayat_name,
            "block_name": p.block_name,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "elevation": p.elevation_mean,
            "rain_prob_pct": round(prob, 1),
            "status": status,
            "is_selected": (p.panchayat_id == selected_panchayat_id),
        })

    map_df = pd.DataFrame(map_df_rows)

    # Plotly Map
    fig = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        color="rain_prob_pct",
        size=[18 if x else 8 for x in map_df["is_selected"]],
        hover_name="panchayat_name",
        hover_data={
            "block_name": True,
            "panchayat_id": True,
            "elevation": True,
            "rain_prob_pct": True,
            "status": True,
            "latitude": False,
            "longitude": False,
        },
        color_continuous_scale="Blues",
        labels={"rain_prob_pct": "Rain ≥1mm (%)", "elevation": "Elevation (m)"},
        mapbox_style="carto-positron",
        zoom=9.2,
        center={"lat": 10.95, "lon": 76.95},
        title=f"Hyperlocal Rainfall Probability & Topography ({lead_time}h Lead Time)",
    )

    # Add IMD Stations Trace
    if stations:
        stn_df = pd.DataFrame(stations)
        fig.add_trace(go.Scattermapbox(
            lat=stn_df["latitude"],
            lon=stn_df["longitude"],
            mode="markers+text",
            marker=dict(size=12, color="#dc2626"),
            text=stn_df["station_id"],
            textposition="top right",
            hovertext=[f"<b>{s['station_id']}</b><br>Elevation: {s.get('station_elevation', 'N/A')}m<br>Host: {s.get('panchayat_name', '')}" for s in stations],
            hoverinfo="text",
            name="IMD Stations",
        ))

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Info footer
    st.markdown(
        """
        <div style="font-size: 0.8rem; color: #64748b; margin-top: 0.5rem;">
            🔴 <strong>Red Markers:</strong> 8 IMD Meteorological Stations &nbsp;|&nbsp;
            🔵 <strong>Blue Circles:</strong> 180 Gram Panchayats (size indicates active selection, color indicates calibrated P(Rain ≥ 1mm)).
        </div>
        """,
        unsafe_allow_html=True,
    )
