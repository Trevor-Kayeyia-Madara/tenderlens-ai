"""MCP Server for TenderLens - Tools for Kenya's OCDS procurement data."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenderlens_mcp")

# Initialize MCP server
server = Server("tenderlens-mcp")

# Kenya OCDS endpoint (using a representative URL - adjust to actual endpoint)
OCDS_BASE_URL = "https://openspending.org/ke-tenders/api/3"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_ocds_data(date_range: Optional[str] = None, limit: int = 100) -> dict[str, Any]:
    """Fetch OCDS data from Kenya's tender portal."""
    params = {"limit": limit}
    if date_range:
        params["date_range"] = date_range

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{OCDS_BASE_URL}/releases", params=params)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Fetched {len(data.get('results', []))} records from OCDS")
        return data


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="ocds_fetch",
            description="Fetch OCDS JSON from Kenya's tender portal with retry logic",
            inputSchema={
                "type": "object",
                "properties": {
                    "date_range": {
                        "type": "string",
                        "description": "Optional date range filter (e.g., '2024-01-01:2024-12-31')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of records to fetch (default: 100)",
                        "default": 100,
                    },
                },
            },
        ),
        Tool(
            name="json_parse",
            description="Extract tender fields from nested OCDS structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "raw_json": {
                        "type": "string",
                        "description": "Raw OCDS JSON response as string",
                    },
                },
                "required": ["raw_json"],
            },
        ),
        Tool(
            name="data_validate",
            description="Validate required fields in tender record",
            inputSchema={
                "type": "object",
                "properties": {
                    "tender_record": {
                        "type": "string",
                        "description": "Parsed tender record as JSON string",
                    },
                },
                "required": ["tender_record"],
            },
        ),
        Tool(
            name="db_store",
            description="Persist validated tender to SQLite database",
            inputSchema={
                "type": "object",
                "properties": {
                    "tender_record": {
                        "type": "string",
                        "description": "Validated tender record as JSON string",
                    },
                    "db_path": {
                        "type": "string",
                        "description": "Path to SQLite database file",
                        "default": "tenders.db",
                    },
                },
                "required": ["tender_record"],
            },
        ),
        Tool(
            name="search_query",
            description="Query tenders with filters (location, category, date, value)",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "Path to SQLite database file",
                        "default": "tenders.db",
                    },
                    "location": {
                        "type": "string",
                        "description": "Filter by buyer location (optional)",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by tender category (optional)",
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Filter by deadline from date (ISO format, optional)",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Filter by deadline to date (ISO format, optional)",
                    },
                    "min_value": {
                        "type": "number",
                        "description": "Minimum contract value (optional)",
                    },
                    "max_value": {
                        "type": "number",
                        "description": "Maximum contract value (optional)",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "ocds_fetch":
            date_range = arguments.get("date_range")
            limit = arguments.get("limit", 100)
            data = await fetch_ocds_data(date_range, limit)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "timestamp": datetime.utcnow().isoformat(),
                            "record_count": len(data.get("results", [])),
                            "data": data,
                        }
                    ),
                )
            ]

        elif name == "json_parse":
            raw_json = arguments["raw_json"]
            parsed = json.loads(raw_json)
            results = parsed.get("results", [])

            parsed_tenders = []
            for record in results:
                # Extract fields from nested OCDS structure
                release = record.get("releases", [{}])[0] if record.get("releases") else {}
                tender = release.get("tender", {})
                planning = release.get("planning", {})
                awards = release.get("awards", [])

                tender_data = {
                    "notice_id": record.get("ocid", ""),
                    "title": tender.get("title", ""),
                    "description": tender.get("description", ""),
                    "deadline": tender.get("tenderPeriod", {}).get("endDate", ""),
                    "buyer_name": release.get("buyer", {}).get("name", ""),
                    "buyer_location": release.get("buyer", {}).get("address", {}).get("region", ""),
                    "status": tender.get("status", ""),
                    "value": tender.get("value", {}).get("amount", 0),
                    "currency": tender.get("value", {}).get("currency", "KES"),
                    "procurement_method": tender.get("procurementMethod", ""),
                    "eligibility_criteria": tender.get("eligibilityCriteria", ""),
                    "award_count": len(awards),
                }
                parsed_tenders.append(tender_data)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "parsed_count": len(parsed_tenders),
                            "tenders": parsed_tenders,
                        }
                    ),
                )
            ]

        elif name == "data_validate":
            tender_record = json.loads(arguments["tender_record"])
            required_fields = ["notice_id", "deadline", "buyer_name", "status"]
            missing_fields = [f for f in required_fields if not tender_record.get(f)]

            is_valid = len(missing_fields) == 0
            has_eligibility = bool(tender_record.get("eligibility_criteria"))

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "valid": is_valid,
                            "missing_fields": missing_fields,
                            "has_eligibility_criteria": has_eligibility,
                            "flag_for_review": not has_eligibility,
                        }
                    ),
                )
            ]

        elif name == "db_store":
            import sqlite3

            tender_record = json.loads(arguments["tender_record"])
            db_path = arguments.get("db_path", "tenders.db")

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create table if not exists
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

            # Insert or update
            cursor.execute(
                """
                INSERT OR REPLACE INTO tenders
                (notice_id, title, description, deadline, buyer_name, buyer_location, status,
                 value, currency, procurement_method, eligibility_criteria, award_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    tender_record.get("notice_id"),
                    tender_record.get("title"),
                    tender_record.get("description"),
                    tender_record.get("deadline"),
                    tender_record.get("buyer_name"),
                    tender_record.get("buyer_location"),
                    tender_record.get("status"),
                    tender_record.get("value"),
                    tender_record.get("currency"),
                    tender_record.get("procurement_method"),
                    tender_record.get("eligibility_criteria"),
                    tender_record.get("award_count"),
                ),
            )

            conn.commit()
            conn.close()

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "notice_id": tender_record.get("notice_id"),
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                )
            ]

        elif name == "search_query":
            import sqlite3

            db_path = arguments.get("db_path", "tenders.db")
            location = arguments.get("location")
            category = arguments.get("category")
            date_from = arguments.get("date_from")
            date_to = arguments.get("date_to")
            min_value = arguments.get("min_value")
            max_value = arguments.get("max_value")

            conn = sqlite3.connect(db_path)
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

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "result_count": len(results),
                            "tenders": results,
                        }
                    ),
                )
            ]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
