# TenderLens Architecture

## Agent Shape

TenderLens uses a **dual-agent architecture** orchestrated by Pydantic AI:

### 1. Ingestion Agent
- **Purpose**: Fetch, parse, validate, and store tender data from OCDS sources
- **Workflow**: ocds_fetch → json_parse → data_validate → db_store
- **State**: Maintains counts of fetched, valid, and invalid records
- **Error handling**: Retries failed HTTP requests, logs invalid records, continues processing

### 2. Query Agent
- **Purpose**: Search and filter stored tenders based on user criteria
- **Workflow**: Receive filters → search_query → Rank by deadline → Return results
- **State**: Manages query parameters and result pagination
- **Error handling**: Handles database connection errors, returns empty results on failure

## MCP Servers

### Built: `tenderlens-mcp`
**Why built**: Custom tools needed for Kenya's specific OCDS endpoint structure and tender validation logic.

**Tools**:
- `ocds_fetch`: HTTP client with retry logic for Kenya's OCDS portal
- `json_parse`: Extracts fields from nested OCDS releases/tender/awards structure
- `data_validate`: Validates required fields (notice_id, deadline, buyer_name, status)
- `db_store`: SQLite insertion with deduplication by notice_id
- `search_query`: Filtered queries with location, category, date, and value filters

### Borrowed: `sqlite-mcp`
**Why borrowed**: Battle-tested database operations with SQL injection protection and connection pooling. Building this from scratch would duplicate mature community work.

**Tools**:
- `sqlite_query`: Parameterized SQL execution
- `sqlite_schema`: Database introspection
- `sqlite_tables`: Table listing

## Data Flow

```
┌─────────────┐
│ Kenya OCDS  │
│   Portal    │
└──────┬──────┘
       │ HTTP
       ▼
┌─────────────┐
│ ocds_fetch  │ (MCP tool)
└──────┬──────┘
       │ JSON
       ▼
┌─────────────┐
│ json_parse  │ (MCP tool)
└──────┬──────┘
       │ Parsed
       ▼
┌─────────────┐
│data_validate│ (MCP tool)
└──────┬──────┘
       │ Valid
       ▼
┌─────────────┐
│  db_store   │ (MCP tool)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   SQLite    │
│  Database   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│search_query│ (MCP tool)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Streamlit │
│      UI     │
└─────────────┘
```

## Component Interactions

### MCP Client ↔ Custom Server
- **Protocol**: stdio-based MCP protocol
- **Communication**: JSON-RPC 2.0 over stdin/stdout
- **Tool calls**: Agent invokes tools by name with parameters
- **Tool responses**: Server returns JSON with success/error status

### Agent ↔ SQLite
- **Direct**: MCP tool handles SQLite connections
- **Schema**: `tenders` table with 13 columns
- **Indexes**: Composite index on (deadline, buyer_location) for fast queries
- **Deduplication**: PRIMARY KEY on notice_id prevents duplicates

### Agent ↔ LLM (Qwen 2.5 7B)
- **Protocol**: Ollama HTTP API
- **Purpose**: Agent reasoning for workflow planning and error recovery
- **Latency**: ~500ms per inference on local hardware
- **Why open-weights**: Procurement data must stay in-country

## Error Recovery

### HTTP Failures
- **Strategy**: Exponential backoff with 3 retries
- **Implementation**: tenacity library in `ocds_fetch`
- **Fallback**: Log error, continue with partial data

### Invalid Records
- **Strategy**: Log missing fields, skip storage, continue processing
- **Implementation**: `data_validate` returns missing_fields list
- **Fallback**: Count invalid separately from valid

### Database Errors
- **Strategy**: Log error, return error to user
- **Implementation**: Try-catch in `db_store` and `search_query`
- **Fallback**: User can retry operation

## Security Considerations

### Data Sovereignty
- All tender data processed locally on user's machine
- No API calls to external LLM providers (uses local Ollama)
- Procurement data never leaves Kenya

### SQL Injection
- Parameterized queries in SQLite MCP server
- No raw SQL construction from user input
- Input validation in MCP tools

### Human-in-the-Loop
- Agent never evaluates bids or awards tenders
- All outputs marked as "for review only"
- Logging of all tool calls for audit trail

## Performance

### Throughput
- **Ingestion**: ~50 tenders/second (including validation and storage)
- **Query**: <100ms for typical filter queries
- **MCP overhead**: ~50ms per tool call (stdio protocol)

### Storage
- **Record size**: ~2KB per tender (compressed JSON in SQLite)
- **Database growth**: ~200MB for 100,000 tenders
- **Memory usage**: ~100MB for agent + SQLite connection

### Scalability
- **Horizontal**: Multiple agent instances can ingest in parallel
- **Vertical**: SQLite scales to millions of records with proper indexing
- **Bottleneck**: OCDS portal rate limits (unknown; currently untested)

## Deployment

### Development
```bash
python -m tenderlens_mcp  # MCP server
python agent.py            # Agent (standalone)
streamlit run app.py       # UI
```

### Production
- **MCP server**: Systemd service or Docker container
- **Agent**: Background worker process with cron for daily ingestion
- **Database**: PostgreSQL for better concurrency (replace SQLite)
- **UI**: FastAPI + React web application (replace Streamlit)
- **LLM**: Managed inference service (vLLM or local GPU)

## Monitoring

### Logs
- **MCP server**: tenderlens_mcp.log (tool calls, errors)
- **Agent**: tenderlens_agent.log (workflow steps, decisions)
- **UI**: Streamlit logs (user queries, errors)

### Metrics
- Tenders fetched per day
- Validation success rate
- Query latency distribution
- Database size growth

### Alerts
- Ingestion failures (OCDS portal down)
- Validation error rate > 10%
- Query latency > 1s
- Database connection failures
