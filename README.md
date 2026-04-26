# GrantFlow MCP Server

A Model Context Protocol (MCP) server that exposes your GrantFlow Django backend as AI-accessible tools, paired with a FastAPI web chat interface powered by Server-Sent Events (SSE).

Ask questions about your grants, budgets, subgrantees, reports, and disbursements in plain English — the agent queries your real Django data in real time and streams its tool calls to the browser as they happen.

---

## What it does

- Wraps your Django REST Framework API as MCP tools
- Runs an OpenAI GPT-4o agent that discovers and calls those tools dynamically
- Streams tool calls and results to the browser in real time via SSE
- Maintains multi-turn conversation history so you can ask follow-up questions
- Works with any MCP-compatible client (Claude Desktop, custom agents, etc.)

---

## Architecture

```
Browser (chat UI)
    ↕ SSE + HTTP
FastAPI (main.py)
    ↕ stdio (MCP protocol)
MCP Server (server.py)
    ↕ HTTP + JWT
Django BGMS Backend
    ↕
MySQL / PostgreSQL
```

---

## Project structure

```
grantflow-mcp/
├── server.py          # MCP server — exposes Django data as tools
├── main.py            # FastAPI app + OpenAI agent + SSE streaming
├── templates/
│   └── index.html     # Chat UI with live tool call feed
├── .env               # Environment variables (never commit this)
├── .env.example       # Template for required variables
└── README.md
```

---

## Requirements

- Python 3.10+
- Django BGMS backend running and accessible
- OpenAI API key
- MTN MoMo / Airtel credentials (optional — only needed for disbursement tools)

---

## Installation

```bash
# 1. Clone or copy the project
cd grantflow-mcp

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install mcp httpx fastapi uvicorn python-multipart \
            jinja2 python-dotenv openai sse-starlette
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
# OpenAI
OPENAI_API_KEY=sk-your-key-here

# Django BGMS backend
DJANGO_BASE_URL=http://localhost:8000
DJANGO_API_TOKEN=eyJhbGci...        # JWT access token
DJANGO_REFRESH_TOKEN=eyJhbGci...    # JWT refresh token
```

### Getting a JWT token from your Django backend

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your-username", "password": "your-password"}'
```

Copy the `access` value into `DJANGO_API_TOKEN` and the `refresh` value into `DJANGO_REFRESH_TOKEN`.

---

## Running the app

```bash
# Terminal 1 — Django backend
cd your-bgms-project
python manage.py runserver

# Terminal 2 — GrantFlow MCP chat
cd grantflow-mcp
source venv/bin/activate
uvicorn main:app --reload
```

Open `http://localhost:8000` in your browser.

---

## Available tools

The MCP server exposes the following tools to the agent:

### Grants
| Tool | Description |
|------|-------------|
| `list_grants` | List all grants, optionally filtered by status or subgrantee |
| `get_grant_detail` | Get full details of a specific grant |

### Budgets
| Tool | Description |
|------|-------------|
| `get_budget_summary` | Total allocated, spent, and remaining balance for a grant |
| `list_budget_categories` | Line-item breakdown by budget category |

### Reports
| Tool | Description |
|------|-------------|
| `list_reports` | List progress reports for a grant, filtered by status |
| `get_report_detail` | Full content of a specific progress report |

### Subgrantees
| Tool | Description |
|------|-------------|
| `list_subgrantees` | List all subgrantees, filtered by region or district |
| `get_subgrantee_detail` | Full profile including bank info and compliance status |

### Disbursements
| Tool | Description |
|------|-------------|
| `list_disbursements` | All disbursements for a grant, filtered by status |
| `get_disbursement_summary` | Financial summary — total disbursed, pending, remaining |

---

## Example questions

Ask anything in the chat — the agent chains tool calls automatically:

```
How many active grants do we currently have?
Which subgrantees are in the Northern region?
What is the budget summary for grant 1?
Show me all pending disbursements for grant 1.
List all reports that have been submitted but not yet approved.
What is the remaining budget across all active grants?
Which subgrantee has the most disbursements?
```

---

## Adapting to your Django URL structure

If your API uses a custom URL prefix or different endpoint naming, update the `_dispatch` function in `server.py`:

```python
# Default (standard DRF)
django_get("/api/grants/")

# Custom prefix
django_get("/api/v1/grants/")
django_get("/bgms/api/grants/")

# Nested budget summary
django_get(f"/api/grants/{grant_id}/budget/summary/")
```

Only the URL strings in `_dispatch` need changing. Tool definitions and the client stay the same.

---

## JWT token refresh

The server automatically refreshes the access token when it expires using the refresh token in `.env`. Your `SIMPLE_JWT` settings determine expiry:

```python
# In Django settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}
```

---

## Connecting to Claude Desktop

To use this MCP server directly in Claude Desktop without the web UI:

1. Find your Claude Desktop config file:
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

2. Add this configuration:

```json
{
  "mcpServers": {
    "grantflow": {
      "command": "python",
      "args": ["/absolute/path/to/grantflow-mcp/server.py"],
      "env": {
        "DJANGO_BASE_URL": "http://localhost:8000",
        "DJANGO_API_TOKEN": "your-access-token",
        "DJANGO_REFRESH_TOKEN": "your-refresh-token"
      }
    }
  }
}
```

3. Restart Claude Desktop — you can now ask Claude about your GrantFlow data directly.

---

## Key concepts

**MCP (Model Context Protocol)** — a standard protocol that separates tool definitions from the agents that use them. You build the server once; any MCP-compatible client can use it without custom integration code.

**SSE (Server-Sent Events)** — one-way push channel from server to browser. Each tool call appears in the UI the moment the agent makes it, rather than waiting for the full response.

**Dynamic tool discovery** — the agent has no hardcoded knowledge of what tools exist. It calls `list_tools()` on connect and adapts automatically. Add a new tool to `server.py` and the agent picks it up on the next connection.

**Multi-turn conversation** — conversation history is maintained in the browser and sent with each request, so the agent has full context for follow-up questions.

---

## Extending the server

To add a new tool:

1. Add a `types.Tool(...)` entry in the `list_tools()` handler in `server.py`
2. Add the corresponding `if name == "your_tool_name":` case in `_dispatch()`
3. Restart the server — the agent picks it up automatically

No changes needed in `main.py` or `index.html`.

---

## Tech stack

| Component | Technology |
|-----------|------------|
| MCP server | `mcp` Python SDK |
| Web framework | FastAPI |
| Real-time streaming | Server-Sent Events (SSE) |
| AI agent | OpenAI GPT-4o via `openai` SDK |
| Django API client | `httpx` |
| Auth | JWT (SimpleJWT) with auto-refresh |
| Frontend | Vanilla HTML/CSS/JS |

---

