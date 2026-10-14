"""Simplified Streamlit UI for TenderLens demo - works on Streamlit Cloud."""

import json
import logging
import os
import sqlite3
from datetime import datetime

import httpx
import streamlit as st

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

# Sidebar for controls
st.sidebar.header("Controls")

# Database setup
def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect("tenders.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tenders (
            notice_id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            deadline TEXT,
            buyer_name TEXT,
            buyer_location TEXT,
            status TEXT,
            value REAL,
            currency TEXT,
            procurement_method TEXT,
            eligibility_criteria TEXT,
            award_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()
    return True

# Fetch OCDS data (simulated for demo)
@st.cache_data(ttl=3600)
def fetch_ocds_data(limit=10):
    """Fetch OCDS data from Kenya's tender portal."""
    # Using a sample endpoint - in production, use actual Kenya OCDS endpoint
    # For demo, we'll return sample data
    sample_tenders = [
        {
            "notice_id": f"OCDS-{i}",
            "title": f"Supply of IT Equipment for {['Ministry of Health', 'County Government of Nairobi', 'Kenya Power', 'Kenya Railways'][i%4]}",
            "description": "Supply and delivery of computers, laptops, and networking equipment",
            "deadline": "2024-12-31",
            "buyer_name": ["Ministry of Health", "County Government of Nairobi", "Kenya Power", "Kenya Railways"][i%4],
            "buyer_location": ["Nairobi", "Nairobi", "Nairobi", "Mombasa"][i%4],
            "status": "active",
            "value": 5000000 + (i * 1000000),
            "currency": "KES",
            "procurement_method": "Open Tender",
            "eligibility_criteria": "Must be registered with KRA and have valid business license",
            "award_count": 0,
        }
        for i in range(limit)
    ]
    return sample_tenders

# Store tenders to database
def store_tenders(tenders):
    """Store tenders to SQLite database."""
    conn = sqlite3.connect("tenders.db")
    cursor = conn.cursor()

    stored_count = 0
    for tender in tenders:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO tenders
                (notice_id, title, description, deadline, buyer_name, buyer_location, status,
                 value, currency, procurement_method, eligibility_criteria, award_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    tender.get("notice_id"),
                    tender.get("title"),
                    tender.get("description"),
                    tender.get("deadline"),
                    tender.get("buyer_name"),
                    tender.get("buyer_location"),
                    tender.get("status"),
                    tender.get("value"),
                    tender.get("currency"),
                    tender.get("procurement_method"),
                    tender.get("eligibility_criteria"),
                    tender.get("award_count"),
                ),
            )
            stored_count += 1
        except Exception as e:
            logger.error(f"Error storing tender {tender.get('notice_id')}: {e}")

    conn.commit()
    conn.close()
    return stored_count

# Search tenders
def search_tenders(location=None, category=None, date_from=None, date_to=None, min_value=None, max_value=None):
    """Search tenders with filters."""
    conn = sqlite3.connect("tenders.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM tenders WHERE 1=1"
    params = []

    if location:
        query += " AND buyer_location LIKE ?"
        params.append(f"%{location}%")
    if category:
        query += " AND title LIKE ?"
        params.append(f"%{category}%")
    if date_from:
        query += " AND deadline >= ?"
        params.append(date_from)
    if date_to:
        query += " AND deadline <= ?"
        params.append(date_to)
    if min_value:
        query += " AND value >= ?"
        params.append(min_value)
    if max_value:
        query += " AND value <= ?"
        params.append(max_value)

    query += " ORDER BY deadline ASC LIMIT 50"

    cursor.execute(query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return results

# Initialize database
if "db_initialized" not in st.session_state:
    st.session_state.db_initialized = init_db()

# Main tabs
tab1, tab2 = st.tabs(["📊 Dashboard", "🔍 Search Tenders"])

with tab1:
    st.header("Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Ingest New Tenders")
        limit = st.number_input("Number of tenders to fetch", min_value=1, max_value=100, value=10)

        if st.button("Start Ingestion"):
            with st.spinner("Ingesting tenders..."):
                try:
                    tenders = fetch_ocds_data(limit=limit)
                    stored = store_tenders(tenders)
                    st.success(f"Ingested {stored} tenders successfully")
                    st.json(tenders[:3])  # Show first 3 as preview
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

    with col2:
        st.subheader("Statistics")
        conn = sqlite3.connect("tenders.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tenders")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tenders WHERE status = 'active'")
        active = cursor.fetchone()[0]
        conn.close()

        st.metric("Total Tenders", total)
        st.metric("Active Tenders", active)

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

    if st.button("Search"):
        with st.spinner("Searching..."):
            try:
                results = search_tenders(
                    location=location or None,
                    category=category or None,
                    date_from=date_from.isoformat() if date_from else None,
                    date_to=date_to.isoformat() if date_to else None,
                    min_value=min_value if min_value > 0 else None,
                    max_value=max_value if max_value > 0 else None,
                )

                st.info(f"Found {len(results)} tenders")

                if results:
                    for tender in results:
                        with st.expander(f"{tender.get('title', 'No title')} - {tender.get('buyer_name', 'Unknown')}"):
                            st.json(tender)
                else:
                    st.warning("No tenders found matching your criteria")
            except Exception as e:
                st.error(f"Search failed: {e}")

# Footer
st.divider()
st.markdown(
    """
    **Human-in-the-Loop**: TenderLens prepares information for review but never evaluates bids or awards tenders.
    All tender decisions are made by human procurement committees.

    **Built with**: MCP + Pydantic AI + SQLite + Streamlit
    """
)
