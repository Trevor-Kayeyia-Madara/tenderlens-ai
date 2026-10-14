# TenderLens

Agentic AI for Kenya's Public Procurement Transparency - making tender opportunities accessible to small suppliers, citizens, and civil society organizations.


## Problem Statement

Small suppliers and citizens across Kenya cannot easily access tender information. Procurement notices, deadlines, and eligibility requirements are scattered across government portals, buried in complex navigation, and often published in formats that are difficult to parse. A small business owner in Mombasa cannot reliably find opportunities relevant to their capacity in Nairobi. A civil society organization cannot track which tenders were awarded and to whom without manual data extraction. This exclusion perpetuates market concentration—larger firms with dedicated procurement teams dominate, while small and local suppliers miss opportunities. Transparency is on paper, but accessibility is the bottleneck.

## Solution Overview

TenderLens is an agentic AI that transforms Kenya's raw OCDS procurement data into an accessible, searchable interface. Using MCP tools, it scrapes tender notices, deadlines, eligibility criteria, and award data from government portals, structures the information, and presents it through a clean dashboard. Small suppliers filter by location, contract size, and category to discover relevant opportunities. Citizens and civil society organizations track award patterns and bidder performance. The agent runs on open-weights models with a human-in-the-loop gate—no bid is evaluated or awarded automatically.

## Target Users

- **Small businesses** lacking dedicated procurement teams
- **Local government oversight bodies**
- **Civil society organizations** monitoring public spending
- **Citizens** interested in government procurement transparency

## Architecture

TenderLens uses a multi-agent architecture with MCP (Model Context Protocol) tool integration:

- **Custom MCP Server**: `tenderlens-mcp` with 5 tools for OCDS data fetching, parsing, validation, storage, and querying
- **Pydantic AI Agent**: Orchestrates the ingestion and query workflows
- **SQLite Database**: Persistent storage for tender records with full-text search
- **Streamlit UI**: Demonstration dashboard for user interaction

## Setup / Installation Instructions

### Option 1: Local Deployment (Ollama)

```bash
# Clone the repository
git clone https://github.com/Trevor-Kayeyia-Madara/tenderlens-ai.git
cd tenderlens-ai

# Install dependencies
pip install -e .

# Install Ollama for local LLM inference
# Visit https://ollama.com and download for your platform
# Pull Qwen 2.5 7B model
ollama pull qwen2.5:7b

# Start Ollama server
ollama serve

# Run the app
streamlit run app.py
```

### Option 2: Cloud Deployment (Groq - Free)

```bash
# Clone the repository
git clone https://github.com/Trevor-Kayeyia-Madara/tenderlens-ai.git
cd tenderlens-ai

# Install dependencies
pip install -e .

# Get a free Groq API key at https://console.groq.com/keys
# Set environment variable
export GROQ_API_KEY="your-api-key-here"

# Run the app
streamlit run app.py
```

Or deploy to Streamlit Cloud:
1. Fork/clone the repository
2. Go to https://share.streamlit.io
3. Connect your GitHub repo
4. Add `GROQ_API_KEY` in the app secrets
5. Deploy

## Usage Instructions

### Running the MCP Server

```bash
# The MCP server is a Python module
python -m tenderlens_mcp
```

### Running the Agent

```bash
# Direct agent usage
python agent.py
```

### Running the Streamlit UI

```bash
# Start the dashboard
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

### Usage Flow

1. **Connect**: Click "Connect to MCP Server" in the sidebar
2. **Ingest**: Fetch new tenders from Kenya's OCDS portal (specify limit and date range)
3. **Search**: Filter tenders by location, category, deadline, and contract value
4. **Review**: Browse results and export relevant opportunities

## Technology Stack

- **Language**: Python 3.11+
- **Orchestration**: Pydantic AI
- **MCP**: Model Context Protocol SDK
- **Database**: SQLite with FTS5 extension
- **LLM**: 
  - Local: Qwen 2.5 7B (via Ollama)
  - Cloud: Llama 3.3 70B (via Groq, free)
- **HTTP**: httpx with tenacity for retry logic
- **Data**: pandas for DataFrame operations, jsonschema for OCDS validation
- **UI**: Streamlit for demonstration dashboard
- **Testing**: pytest for evals

## Agent Architecture

### Agents

- **Ingestion Agent**: Fetches OCDS data, parses JSON, validates required fields, stores to database
- **Query Agent**: Handles user search requests, applies filters, returns ranked results

### LLMs

- **Local**: Qwen 2.5 7B (open-weights via Ollama) for in-country data processing
- **Cloud**: Llama 3.3 70B (via Groq, free API) for global deployment
- **Secondary**: GPT-4o for synthetic test data generation only (demonstration purposes)

### Memory

- **Short-term**: In-memory state for ongoing workflow steps in Pydantic AI
- **Long-term**: SQLite database for persistent tender storage and query history

### Orchestration

- **Pydantic AI**: Type-safe agentic workflows with structured state management and error recovery
- **State Machine**: Transitions through ingest → validate → structure → store → query stages

## MCP Implementation

### Custom MCP Server: `tenderlens-mcp`

Built with MCP Python SDK, exposes 5 tools:

1. **`ocds_fetch`** - Retrieves OCDS JSON from Kenya's tender portal with retry logic
2. **`json_parse`** - Extracts tender fields from nested OCDS structure
3. **`data_validate`** - Validates required fields (notice_id, deadline, buyer_name, status)
4. **`db_store`** - Persists validated tenders to SQLite with deduplication
5. **`search_query`** - Queries tenders with filters (location, category, date, value)

### Community MCP Server: `sqlite-mcp`

Borrowed for robust database operations (`sqlite_query`, `sqlite_schema`). Avoids duplicating mature community work.

### Connection to Agent

Pydantic AI agent connects to both MCP servers via MCP client. Tools are called as first-class functions in the workflow:

- **Ingestion**: `ocds_fetch` → `json_parse` → `data_validate` → `db_store`
- **Query**: User filters → `search_query` → ranked results
- **Error recovery**: Retries on fetch failures, logs invalid records, continues processing

### Resources

- OCDS Schema JSON (for validation)
- Kenya Tender Portal API (external data source)

## MCP Tools / Servers

### Custom Server: `tenderlens-mcp`

- `ocds_fetch`: HTTP client for OCDS endpoint with retry logic
- `json_parse`: Validates and extracts tender fields from OCDS JSON
- `data_validate`: Checks required fields and flags incomplete records
- `db_store`: Inserts validated tenders into SQLite with deduplication
- `search_query`: Filters tenders by location, category, date range, contract value

### Community Server: `sqlite-mcp`

- `sqlite_query`: Execute SQL queries with parameter binding
- `sqlite_schema`: Inspect database structure
- `sqlite_tables`: List available tables

## Human-in-the-Loop Workflow

TenderLens implements a strict human-in-the-loop pattern:

1. **Agent prepares data**: Fetches, parses, validates, and structures tender information
2. **Agent stops**: Never evaluates bids, never awards tenders, never makes procurement decisions
3. **Human reviews**: Named procurement officer or committee reviews the prepared information
4. **Human decides**: Committee makes the final decision on awarding tenders

Every tool call is logged with inputs, outputs, timestamps, and approval status before any information reaches users.

## Limitations

- **Data availability**: Kenya's OCDS portal may have rate limits or downtime
- **Data quality**: Some tender records may be incomplete or inconsistent
- **Local LLM performance**: Qwen 2.5 7B may have lower accuracy than frontier models for complex reasoning
- **Scope**: Currently focuses on Kenya's procurement data; other countries require endpoint configuration
- **UI**: Streamlit dashboard is for demonstration; production would need a web application

## Future Improvements

- **Multi-country support**: Add support for Rwanda, Tanzania, Nigeria, and other African OCDS publishers
- **Alert system**: Notify users when tenders matching their criteria are published
- **Analytics dashboard**: Track award patterns, bidder performance, and spending trends
- **Mobile app**: USSD or mobile web interface for users without reliable internet
- **Email integration**: Send daily tender digests to subscribed users
- **Advanced search**: Natural language queries, semantic search across tender descriptions
- **Collaboration features**: Allow teams to share tender lists and annotations

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Citation

If you use TenderLens in your work, please cite:

```
TenderLens: Agentic AI for Kenya's Public Procurement Transparency
```

## Contact

For questions or collaboration, please open an issue on GitHub.
