"""
GramDrishti — Forecast Reliability Component (Phase 7 Integration Boundary)
"""

from typing import Optional, Dict, Any
import streamlit as st
from app.formatting import get_badge_html, get_reliability_badge


def render_reliability_section(reliability_data: Optional[Dict[str, Any]] = None):
    """Renders the forecast reliability assessment section."""
    st.markdown("### 🛡️ Forecast Reliability & Limitations")

    if reliability_data is None:
        st.markdown(
            """
            <div style="background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 10px; padding: 1.5rem; text-align: center; margin-bottom: 1.5rem;">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">📋</div>
                <div style="font-weight: 600; color: #475569; font-size: 1.05rem;">
                    Reliability information unavailable.
                </div>
                <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.4rem;">
                    Phase 7 reliability artifacts are not present in this deployment.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### 🔬 Empirical Validation Baselines (Phase 5 & 6 Factual Ground Truth)")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                f"""
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem;">
                    <div style="font-weight: 700; color: #0f172a; margin-bottom: 0.5rem;">Variable UQ & Calibration</div>
                    <table style="width: 100%; font-size: 0.85rem; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #f1f5f9; height: 32px;">
                            <td><strong>Temperature UQ</strong></td>
                            <td style="text-align: right;">{get_reliability_badge("HIGH")}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #f1f5f9; height: 32px;">
                            <td><strong>Humidity UQ</strong></td>
                            <td style="text-align: right;">{get_reliability_badge("LOW")}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #f1f5f9; height: 32px;">
                            <td><strong>Rainfall ≥ 1.0 mm</strong></td>
                            <td style="text-align: right;">{get_reliability_badge("MEDIUM")}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #f1f5f9; height: 32px;">
                            <td><strong>Rainfall ≥ 10.0 mm</strong></td>
                            <td style="text-align: right;">{get_reliability_badge("NOT_EVALUABLE")}</td>
                        </tr>
                        <tr style="height: 32px;">
                            <td><strong>Rainfall ≥ 25.0 mm</strong></td>
                            <td style="text-align: right;">{get_reliability_badge("NOT_EVALUABLE")}</td>
                        </tr>
                    </table>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.markdown(
                """
                <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; font-size: 0.82rem; color: #334155; line-height: 1.5;">
                    <div style="font-weight: 700; color: #0f172a; margin-bottom: 0.5rem;">Documented Reason Codes</div>
                    <ul style="margin: 0; padding-left: 1.2rem;">
                        <li><strong>Temperature:</strong> Conformal coverage 87.7% on TEST. Consistent error bounds.</li>
                        <li><strong>Humidity:</strong> Low test coverage (20.15%) caused by strong summer seasonal shift.</li>
                        <li><strong>Rainfall ≥1mm:</strong> Isotonic calibration applied on 720 CALIB records.</li>
                        <li><strong>Rainfall ≥10mm:</strong> 0 events in TRAIN/CALIB, un-trainable under split.</li>
                        <li><strong>Rainfall ≥25mm:</strong> 0 events across entire historical record.</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown("#### Phase 7 Assessed Reliability")
        st.json(reliability_data)
