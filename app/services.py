"""
GramDrishti — Application Services Layer
=========================================
Encapsulates business logic, data filtering, aggregations, and Plotly chart generation.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from app.data_loader import DataLoader
from app.schemas import (
    PanchayatInfo,
    WeatherForecastData,
    RainfallForecastData,
    SystemStatusReport,
    FreshnessStatus,
    AggregationStatus,
)


class ForecastService:
    """Service providing weather and rainfall forecasts to the UI."""

    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or DataLoader()
        self._panchayats_cache: Optional[List[PanchayatInfo]] = None
        self._stations_cache: Optional[List[Dict[str, Any]]] = None

    def get_all_panchayats(self) -> List[PanchayatInfo]:
        """Retrieves list of all 180 Panchayats."""
        if self._panchayats_cache is None:
            self._panchayats_cache = self.loader.load_panchayats()
        return self._panchayats_cache

    def get_panchayat_by_id(self, panchayat_id: str) -> Optional[PanchayatInfo]:
        """Finds a specific Panchayat by ID."""
        for p in self.get_all_panchayats():
            if p.panchayat_id == panchayat_id:
                return p
        return None

    def get_all_stations(self) -> List[Dict[str, Any]]:
        """Retrieves list of 8 IMD Observation Stations."""
        if self._stations_cache is None:
            self._stations_cache = self.loader.load_stations_metadata()
        return self._stations_cache

    def get_available_lead_times(self) -> List[int]:
        """Returns available forecast lead times [24, 48, 72]."""
        return [24, 48, 72]

    def get_available_dates(self) -> List[str]:
        """Returns list of available forecast observation dates."""
        df_pr = self.loader.load_panchayat_rainfall_df()
        if not df_pr.empty and "timestamp" in df_pr:
            return sorted(df_pr["timestamp"].unique().tolist())
        df_w = self.loader.load_weather_forecasts_df()
        if not df_w.empty and "observation_time" in df_w:
            return sorted(df_w["observation_time"].unique().tolist())
        return ["2024-05-01"]

    def get_panchayat_view_data(
        self,
        panchayat_id: str,
        timestamp: Optional[str] = None,
        lead_time: int = 24
    ) -> Dict[str, Any]:
        """Assembles all relevant view data for a selected Panchayat."""
        p_info = self.get_panchayat_by_id(panchayat_id)
        if not p_info:
            return {"error": f"Panchayat {panchayat_id} not found."}

        # 1. Fetch rainfall forecast
        rain_fc = self.loader.get_panchayat_rainfall_forecast(
            panchayat_id=panchayat_id,
            timestamp=timestamp,
            lead_time=lead_time,
        )

        # 2. Fetch associated / nearest station weather forecast
        stn_id = p_info.nearest_station_id or "STN_CBE_01"
        weather_fc = self.loader.get_station_weather_forecast(
            station_id=stn_id,
            timestamp=timestamp,
            lead_time=lead_time,
        )

        # 3. Check Phase 7 reliability & advisory
        p7_rel_df = self.loader.load_phase7_reliability()
        p7_adv = self.loader.load_phase7_advisories()

        p7_rel_data = None
        if p7_rel_df is not None and not p7_rel_df.empty:
            sub = p7_rel_df[p7_rel_df["panchayat_id"] == panchayat_id]
            if not sub.empty:
                p7_rel_data = sub.iloc[-1].to_dict()

        return {
            "panchayat": p_info,
            "rainfall_forecast": rain_fc,
            "weather_forecast": weather_fc,
            "station_id": stn_id,
            "phase7_reliability": p7_rel_data,
            "phase7_advisory": p7_adv,
            "timestamp": timestamp or (rain_fc.timestamp if rain_fc else None),
            "lead_time": lead_time,
        }

    # -------------------------------------------------------------
    # Plotly Chart Generators
    # -------------------------------------------------------------
    @staticmethod
    def create_uncertainty_gauge(
        val: Optional[float],
        p10: Optional[float],
        p50: Optional[float],
        p90: Optional[float],
        title: str,
        unit: str,
        color: str = "#2563eb"
    ) -> Optional[go.Figure]:
        """Creates an uncertainty interval whisker / box plot."""
        if p10 is None or p90 is None or val is None:
            return None

        fig = go.Figure()

        # Uncertainty band (P10 to P90)
        fig.add_trace(go.Scatter(
            x=[p10, p90],
            y=[0, 0],
            mode="lines+markers",
            line=dict(color=color, width=6),
            marker=dict(size=12, symbol="line-ns-open", color=color, line=dict(width=3, color=color)),
            name="80% Conformal Interval (P10–P90)",
            hoverinfo="text",
            text=[f"P10: {p10:.1f}{unit}", f"P90: {p90:.1f}{unit}"],
        ))

        # Median marker (P50)
        med_val = p50 if p50 is not None else val
        fig.add_trace(go.Scatter(
            x=[med_val],
            y=[0],
            mode="markers+text",
            marker=dict(size=14, color="#1e293b", symbol="diamond"),
            name="P50 Median",
            text=[f"P50: {med_val:.1f}{unit}"],
            textposition="top center",
        ))

        # Predicted Value marker
        fig.add_trace(go.Scatter(
            x=[val],
            y=[0],
            mode="markers",
            marker=dict(size=12, color="#dc2626", symbol="circle"),
            name="Predicted Value",
            hoverinfo="text",
            text=[f"Prediction: {val:.1f}{unit}"],
        ))

        fig.update_layout(
            title=dict(text=title, font=dict(size=14, color="#1e293b")),
            xaxis=dict(
                title=f"{unit}",
                showgrid=True,
                zeroline=False,
                range=[p10 - (p90 - p10) * 0.3, p90 + (p90 - p10) * 0.3],
            ),
            yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.5, 0.5]),
            height=140,
            margin=dict(l=20, r=20, t=35, b=25),
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,250,252,0.6)",
        )
        return fig

    @staticmethod
    def create_baseline_comparison_chart(weather_fc: WeatherForecastData, metric: str = "temperature") -> Optional[go.Figure]:
        """Creates bar chart comparing B0, B1, B2, B3, ML model and Observed value."""
        if metric == "temperature":
            models = ["B0 Raw NWP", "B1 Lapse Rate", "B2 Geospatial", "B3 Quantile", "ML Residual Model", "Observed Target"]
            vals = [
                weather_fc.b0_temperature,
                weather_fc.b1_temperature,
                weather_fc.b2_temperature,
                weather_fc.b3_temperature,
                weather_fc.ml_temperature,
                weather_fc.observed_temperature,
            ]
            unit = "°C"
            colors = ["#94a3b8", "#64748b", "#38bdf8", "#818cf8", "#2563eb", "#16a34a"]
        else:
            models = ["B0 Raw NWP", "B1 Lapse Rate", "B2 Geospatial", "B3 Quantile", "ML Residual Model", "Observed Target"]
            vals = [
                weather_fc.b0_humidity,
                weather_fc.b1_humidity,
                weather_fc.b2_humidity,
                weather_fc.b3_humidity,
                weather_fc.ml_humidity,
                weather_fc.observed_humidity,
            ]
            unit = "%"
            colors = ["#94a3b8", "#64748b", "#38bdf8", "#818cf8", "#0284c7", "#16a34a"]

        # Filter available
        labels = []
        data = []
        bar_colors = []
        for m, v, c in zip(models, vals, colors):
            if v is not None and not np.isnan(v):
                labels.append(m)
                data.append(v)
                bar_colors.append(c)

        if not data:
            return None

        fig = go.Figure(data=[
            go.Bar(
                x=labels,
                y=data,
                marker=dict(color=bar_colors),
                text=[f"{v:.1f}{unit}" for v in data],
                textposition="auto",
            )
        ])
        fig.update_layout(
            title=f"{metric.capitalize()} Model Comparison ({weather_fc.lead_time_hours}h Lead Time)",
            yaxis=dict(title=unit),
            height=320,
            margin=dict(l=30, r=20, t=40, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,250,252,0.6)",
        )
        return fig

    @staticmethod
    def create_rainfall_timeline_chart(panchayat_id: str, loader: DataLoader) -> Optional[go.Figure]:
        """Creates line chart of rainfall probability over time for 24h, 48h, 72h lead times."""
        df = loader.load_panchayat_rainfall_df()
        if df.empty:
            return None
        sub = df[df["panchayat_id"] == panchayat_id]
        if sub.empty:
            return None

        fig = go.Figure()
        colors = {24: "#2563eb", 48: "#7c3aed", 72: "#db2777"}

        for lt in [24, 48, 72]:
            sub_lt = sub[sub["lead_time"] == lt].sort_values("timestamp")
            if not sub_lt.empty:
                probs = sub_lt["rain_probability_1mm"] * 100.0
                fig.add_trace(go.Scatter(
                    x=sub_lt["timestamp"],
                    y=probs,
                    mode="lines+markers",
                    name=f"{lt}h Lead Time",
                    line=dict(color=colors.get(lt, "#2563eb"), width=2),
                ))

        fig.update_layout(
            title="Rainfall Probability P(Rain ≥ 1mm) Across May–June 2024",
            xaxis=dict(title="Forecast Date"),
            yaxis=dict(title="Probability (%)", range=[0, max(25, sub['rain_probability_1mm'].max() * 100 * 1.2)]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=320,
            margin=dict(l=30, r=20, t=40, b=40),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(248,250,252,0.6)",
        )
        return fig
