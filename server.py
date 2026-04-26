import os
import json
import httpx
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

load_dotenv()

BASE_URL = os.getenv("DJANGO_BASE_URL", "http://localhost:8000")
API_TOKEN = os.getenv("DJANGO_API_TOKEN", "")


    

# ── Token ──────────────────────────────────────────


REFRESH_TOKEN = os.getenv("DJANGO_REFRESH_TOKEN", "")

def refresh_access_token() -> str:
    """Get a fresh access token using the refresh token."""
    with httpx.Client() as client:
        response = client.post(
            f"{BASE_URL}/api/auth/refresh/",
            json={"refresh": REFRESH_TOKEN},
        )
        response.raise_for_status()
        return response.json()["access"]
    
def django_get(path: str, params: dict = None) -> dict | list:
    """GET with automatic token refresh on 401."""
    with httpx.Client(timeout=15) as client:
        response = client.get(
            f"{BASE_URL}{path}",
            headers=get_headers(),
            params=params or {},
        )
        if response.status_code == 401 and REFRESH_TOKEN:
            # Token expired — refresh and retry once
            new_token = refresh_access_token()
            os.environ["DJANGO_API_TOKEN"] = new_token
            response = client.get(
                f"{BASE_URL}{path}",
                headers=get_headers(),
                params=params or {},
            )
        response.raise_for_status()
        return response.json()
    


# ── Django API helper ──────────────────────────────────────────

def get_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:      
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers


def django_get(path: str, params: dict = None) -> dict | list:
    """Make a GET request to the Django backend."""
    with httpx.Client(timeout=15) as client:
        response = client.get(
            f"{BASE_URL}{path}",
            headers=get_headers(),
            params=params or {},
        )
        response.raise_for_status()
        return response.json()


def django_post(path: str, data: dict) -> dict:
    """Make a POST request to the Django backend."""
    with httpx.Client(timeout=15) as client:
        response = client.post(
            f"{BASE_URL}{path}",
            headers=get_headers(),
            json=data,
        )
        response.raise_for_status()
        return response.json()


# ── MCP Server ─────────────────────────────────────────────────

app = Server("grantflow-mcp")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """
    Declare all tools this MCP server exposes.
    Every MCP client sees this list and knows what it can call.
    """
    return [

        # ── Grants ─────────────────────────────────────────────
        types.Tool(
            name="list_grants",
            description=(
                "List all grants in the GrantFlow system. "
                "Optionally filter by status (active, closed, pending) "
                "or subgrantee name."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by grant status: active, closed, pending",
                        "enum": ["active", "closed", "pending"],
                    },
                    "subgrantee": {
                        "type": "string",
                        "description": "Filter by subgrantee name (partial match)",
                    },
                },
                "required": [],
            },
        ),

        types.Tool(
            name="get_grant_detail",
            description=(
                "Get full details of a specific grant including objectives, "
                "timeline, total budget, and current status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grant_id": {
                        "type": "integer",
                        "description": "The ID of the grant to retrieve",
                    },
                },
                "required": ["grant_id"],
            },
        ),

        # ── Budgets ────────────────────────────────────────────
        types.Tool(
            name="get_budget_summary",
            description=(
                "Get the budget summary for a grant — total allocated, "
                "total spent, remaining balance, and breakdown by budget category."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grant_id": {
                        "type": "integer",
                        "description": "The grant ID to get budget summary for",
                    },
                },
                "required": ["grant_id"],
            },
        ),

        types.Tool(
            name="list_budget_categories",
            description=(
                "List all budget categories and their allocations for a grant. "
                "Shows planned vs actual spend per category."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grant_id": {
                        "type": "integer",
                        "description": "The grant ID",
                    },
                },
                "required": ["grant_id"],
            },
        ),

        # ── Reports ────────────────────────────────────────────
        types.Tool(
            name="list_reports",
            description=(
                "List progress reports submitted for a grant. "
                "Shows report period, submission date, and approval status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grant_id": {
                        "type": "integer",
                        "description": "The grant ID to list reports for",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by report status: submitted, approved, rejected",
                        "enum": ["submitted", "approved", "rejected"],
                    },
                },
                "required": ["grant_id"],
            },
        ),

        types.Tool(
            name="get_report_detail",
            description=(
                "Get the full content of a specific progress report "
                "including narrative, achievements, challenges, and next steps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "report_id": {
                        "type": "integer",
                        "description": "The report ID to retrieve",
                    },
                },
                "required": ["report_id"],
            },
        ),

        # ── Subgrantees ────────────────────────────────────────
        types.Tool(
            name="list_subgrantees",
            description=(
                "List all subgrantee organisations in the system. "
                "Shows name, district, region, and active grant count."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "Filter by region name",
                    },
                    "district": {
                        "type": "string",
                        "description": "Filter by district name",
                    },
                },
                "required": [],
            },
        ),

        types.Tool(
            name="get_subgrantee_detail",
            description=(
                "Get full profile of a subgrantee including contact details, "
                "bank information, all their grants, and compliance status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subgrantee_id": {
                        "type": "integer",
                        "description": "The subgrantee ID to retrieve",
                    },
                },
                "required": ["subgrantee_id"],
            },
        ),

        # ── Disbursements ──────────────────────────────────────
        types.Tool(
            name="list_disbursements",
            description=(
                "List all disbursements (payments) made for a grant. "
                "Shows amount, date, payment method, and status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grant_id": {
                        "type": "integer",
                        "description": "The grant ID to list disbursements for",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status: pending, completed, failed",
                        "enum": ["pending", "completed", "failed"],
                    },
                },
                "required": ["grant_id"],
            },
        ),

        types.Tool(
            name="get_disbursement_summary",
            description=(
                "Get a financial summary of all disbursements for a grant — "
                "total disbursed, pending, and remaining to disburse."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "grant_id": {
                        "type": "integer",
                        "description": "The grant ID",
                    },
                },
                "required": ["grant_id"],
            },
        ),

    ]


@app.call_tool()
async def call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent]:
    """
    Handle every tool call from the MCP client.
    Routes to the correct Django endpoint and returns the result.
    """
    try:
        result = await _dispatch(name, arguments)
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )]
    except httpx.HTTPStatusError as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({
                "error": f"Django API error: {e.response.status_code}",
                "detail": e.response.text,
            }),
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e)}),
        )]


async def _dispatch(name: str, args: dict) -> dict | list:
    """Route tool name to the correct Django API call."""

    # ── Grants ─────────────────────────────────────────────────
    if name == "list_grants":
        params = {}
        if args.get("status"):    params["status"]     = args["status"]
        if args.get("subgrantee"): params["subgrantee"] = args["subgrantee"]
        return django_get("/api/grants/list/", params)

    if name == "get_grant_detail":
        return django_get(f"/api/grants/{args['grant_id']}/")

    # ── Budgets ────────────────────────────────────────────────
    if name == "get_budget_summary":
        return django_get(f"/api/grants/{args['grant_id']}/budget-summary/")

    if name == "list_budget_categories":
        return django_get("/api/budget-categories/", {"grant": args["grant_id"]})

    # ── Reports ────────────────────────────────────────────────
    if name == "list_reports":
        params = {"grant": args["grant_id"]}
        if args.get("status"): params["status"] = args["status"]
        return django_get("/api/reports/finance-reports/", params)

    if name == "get_report_detail":
        return django_get(f"/api/reports/{args['report_id']}/")

    # ── Subgrantees ────────────────────────────────────────────
    if name == "list_subgrantees":
        params = {}
        if args.get("region"):   params["region"]   = args["region"]
        if args.get("district"): params["district"] = args["district"]
        return django_get("/api/subgrantees/subgrantee-profiles/", params)

    if name == "get_subgrantee_detail":
        return django_get(f"/api/subgrantees/{args['subgrantee_id']}/")

    # ── Disbursements ──────────────────────────────────────────
    if name == "list_disbursements":
        params = {"grant": args["grant_id"]}
        if args.get("status"): params["status"] = args["status"]
        return django_get("/api/request/all-requests/", params)

    if name == "get_disbursement_summary":
        return django_get(
            f"/api/grants/{args['grant_id']}/disbursement-summary/"
        )

    raise ValueError(f"Unknown tool: {name}")


# ── Entry point ─────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())