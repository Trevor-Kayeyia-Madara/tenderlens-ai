"""Streamlit UI for TenderLens demo."""

import asyncio
import json
import logging
from datetime import datetime

import streamlit as st
from agent import TenderLensAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenderlens_ui")

# Configure Streamlit page
st.set_page_config(
    page_title="TenderLens - Kenya's Public Procurement Portal",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 TenderLens")
st.markdown(
    """
    **Agentic AI for Kenya's Public Procurement Transparency**

    TenderLens makes Kenya's OCDS procurement data accessible to small suppliers, citizens,
    and civil society organizations. Find tender opportunities, track awards, and understand
    public spending patterns.

    *Built for the Agentic AI for Africa Innovation Challenge*
    """
)

# Initialize agent in session state
if "agent" not in st.session_state:
    st.session_state.agent = TenderLensAgent()
    st.session_state.connected = False

# Sidebar for controls
st.sidebar.header("Controls")

# Connect/Disconnect button
if st.sidebar.button("Connect to MCP Server"):
    if not st.session_state.connected:
        try:
            asyncio.run(st.session_state.agent.connect_mcp())
            st.session_state.connected = True
            st.sidebar.success("Connected!")
        except Exception as e:
            st.sidebar.error(f"Connection failed: {e}")
    else:
        st.sidebar.info("Already connected")

# Main tabs
tab1, tab2 = st.tabs(["📊 Dashboard", "🔍 Search Tenders"])

with tab1:
    st.header("Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Ingest New Tenders")
        limit = st.number_input("Number of tenders to fetch", min_value=1, max_value=1000, value=50)
        date_range = st.text_input("Date range (optional, e.g., 2024-01-01:2024-12-31)")

        if st.button("Start Ingestion") and st.session_state.connected:
            with st.spinner("Ingesting tenders..."):
                try:
                    result = asyncio.run(
                        st.session_state.agent.ingest_tenders(date_range=date_range or None, limit=limit)
                    )
                    st.json(result)
                    st.success(f"Ingested {result.get('valid', 0)} valid tenders")
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")
        elif not st.session_state.connected:
            st.warning("Please connect to MCP server first")

    with col2:
        st.subheader("Statistics")
        st.info("Database statistics will appear here after ingestion")

with tab2:
    st.header("Search Tenders")

    col1, col2, col3 = st.columns(3)

    with col1:
        location = st.text_input("Location (e.g., Nairobi)")
        category = st.text_input("Category (e.g., IT, Construction)")

    with col2:
        date_from = st.date_input("Deadline from")
        date_to = st.date_input("Deadline to")

    with col3:
        min_value = st.number_input("Min value (KES)", min_value=0.0, value=0.0)
        max_value = st.number_input("Max value (KES)", min_value=0.0, value=0.0)

    if st.button("Search") and st.session_state.connected:
        with st.spinner("Searching..."):
            try:
                result = asyncio.run(
                    st.session_state.agent.search_tenders(
                        location=location or None,
                        category=category or None,
                        date_from=date_from.isoformat() if date_from else None,
                        date_to=date_to.isoformat() if date_to else None,
                        min_value=min_value if min_value > 0 else None,
                        max_value=max_value if max_value > 0 else None,
                    )
                )

                if result.get("success"):
                    tenders = result.get("tenders", [])
                    st.info(f"Found {len(tenders)} tenders")

                    if tenders:
                        for tender in tenders:
                            with st.expander(f"{tender.get('title', 'No title')} - {tender.get('buyer_name', 'Unknown')}"):
                                st.json(tender)
                    else:
                        st.warning("No tenders found matching your criteria")
                else:
                    st.error("Search failed")
            except Exception as e:
                st.error(f"Search failed: {e}")
    elif not st.session_state.connected:
        st.warning("Please connect to MCP server first")

# Footer
st.divider()
st.markdown(
    """
    **Human-in-the-Loop**: TenderLens prepares information for review but never evaluates bids or awards tenders.
    All tender decisions are made by human procurement committees.

    **Built with**: MCP + Pydantic AI + SQLite + Qwen 2.5 (open-weights)
    """
)
