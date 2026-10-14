"""TenderLens Agent - Pydantic AI agent for tender ingestion and querying."""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tenderlens_agent")


class TenderLensAgent:
    """Agentic AI for Kenya's public procurement transparency."""

    def __init__(self, mcp_server_path: str = "tenderlens_mcp"):
        self.mcp_server_path = mcp_server_path
        self.mcp_session: Optional[ClientSession] = None
        self.agent: Optional[Agent] = None

        # Use Groq for cloud deployment (free, fast)
        # Set GROQ_API_KEY environment variable, or use placeholder
        groq_api_key = os.getenv("GROQ_API_KEY", "")
        if groq_api_key:
            self.model = OpenAIModel(
                "groq/llama-3.3-70b-versatile",
                base_url="https://api.groq.com/openai/v1",
                api_key=groq_api_key,
            )
        else:
            # Fallback to local model if no API key
            logger.warning("GROQ_API_KEY not set, using local model placeholder")
            self.model = "qwen2.5:7b"  # Will fail without Ollama, used as placeholder

    async def connect_mcp(self) -> None:
        """Connect to the custom MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=["-m", self.mcp_server_path],
        )

        self.mcp_session = ClientSession(server_params)
        await self.mcp_session.__aenter__()

        # Initialize the agent with MCP tools
        self.agent = Agent(
            self.model,
            system_prompt=(
                "You are TenderLens, an agentic AI that helps users discover and understand "
                "public procurement opportunities in Kenya. You fetch tender data from OCDS sources, "
                "validate it, store it, and query it based on user filters. "
                "You never evaluate bids or award tenders - you only prepare information for review. "
                "Always cite the source of your findings."
            ),
        )

        logger.info("Connected to MCP server and initialized agent")

    async def ingest_tenders(
        self, date_range: Optional[str] = None, limit: int = 100
    ) -> dict[str, Any]:
        """Ingest tenders from OCDS source."""
        if not self.mcp_session:
            raise RuntimeError("MCP session not connected")

        logger.info(f"Starting tender ingestion: date_range={date_range}, limit={limit}")

        # Step 1: Fetch OCDS data
        fetch_result = await self.mcp_session.call_tool(
            "ocds_fetch", {"date_range": date_range, "limit": limit}
        )
        fetch_data = json.loads(fetch_result[0].text)

        if not fetch_data.get("success"):
            logger.error("Failed to fetch OCDS data")
            return {"success": False, "error": "Failed to fetch OCDS data"}

        # Step 2: Parse JSON
        parse_result = await self.mcp_session.call_tool(
            "json_parse", {"raw_json": json.dumps(fetch_data["data"])}
        )
        parse_data = json.loads(parse_result[0].text)

        parsed_tenders = parse_data.get("tenders", [])
        logger.info(f"Parsed {len(parsed_tenders)} tenders")

        # Step 3: Validate and store each tender
        valid_count = 0
        invalid_count = 0
        for tender in parsed_tenders:
            validate_result = await self.mcp_session.call_tool(
                "data_validate", {"tender_record": json.dumps(tender)}
            )
            validate_data = json.loads(validate_result[0].text)

            if validate_data.get("valid"):
                store_result = await self.mcp_session.call_tool(
                    "db_store", {"tender_record": json.dumps(tender)}
                )
                if json.loads(store_result[0].text).get("success"):
                    valid_count += 1
            else:
                invalid_count += 1
                logger.warning(
                    f"Invalid tender {tender.get('notice_id')}: {validate_data.get('missing_fields')}"
                )

        logger.info(f"Ingestion complete: {valid_count} valid, {invalid_count} invalid")

        return {
            "success": True,
            "fetched": len(parsed_tenders),
            "valid": valid_count,
            "invalid": invalid_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def search_tenders(
        self,
        location: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ) -> dict[str, Any]:
        """Search tenders with filters."""
        if not self.mcp_session:
            raise RuntimeError("MCP session not connected")

        logger.info(f"Searching tenders with filters: {locals()}")

        search_params = {}
        if location:
            search_params["location"] = location
        if category:
            search_params["category"] = category
        if date_from:
            search_params["date_from"] = date_from
        if date_to:
            search_params["date_to"] = date_to
        if min_value:
            search_params["min_value"] = min_value
        if max_value:
            search_params["max_value"] = max_value

        search_result = await self.mcp_session.call_tool("search_query", search_params)
        search_data = json.loads(search_result[0].text)

        logger.info(f"Found {search_data.get('result_count', 0)} tenders")

        return search_data

    async def close(self) -> None:
        """Close MCP session."""
        if self.mcp_session:
            await self.mcp_session.__aexit__(None, None, None)
            logger.info("Closed MCP session")


async def main():
    """Main entry point for testing."""
    agent = TenderLensAgent()
    await agent.connect_mcp()

    try:
        # Example: Ingest some tenders
        result = await agent.ingest_tenders(limit=10)
        print(f"Ingestion result: {result}")

        # Example: Search tenders
        search_result = await agent.search_tenders(location="Nairobi")
        print(f"Search result: {search_result}")

    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
