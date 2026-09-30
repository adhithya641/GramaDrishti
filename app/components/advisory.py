"""
GramDrishti — Crop Advisory Component (Phase 7 Integration Boundary)
"""

from typing import Optional, Dict, Any
import streamlit as st


def render_advisory_section(advisory_data: Optional[Dict[str, Any]] = None):
    """Renders the agricultural crop advisory section."""
    st.markdown("### 🌾 Crop Advisory")

    if advisory_data is None:
        st.markdown(
            """
            <div style="background-color: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 10px; padding: 1.5rem; text-align: center;">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">🚜</div>
                <div style="font-weight: 600; color: #475569; font-size: 1.05rem;">
                    Advisory engine data is not available in this deployment.
                </div>
                <div style="font-size: 0.85rem; color: #64748b; margin-top: 0.5rem; max-width: 500px; margin-left: auto; margin-right: auto;">
                    Phase 7 (Agronomic Rule Engine & Advisory Synthesis) is undergoing evaluation on a separate deployment pipeline. Phase 8 strictly presents verified data without inventing synthetic crop recommendations.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"**Advisory Bulletin:** {advisory_data.get('title', 'Local Advisory')}")
        st.write(advisory_data.get("content", "Advisory content available."))
