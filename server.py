"""
GF Data MCP Server — connects Claude Desktop to gfdata.sigmify.com.

This is an aggregated M&A comps database. The API returns deal statistics
(TEV/EBITDA, TEV/Rev, margins, etc.) grouped by year/quarter or by deal-size
(TEV) range, with filters for industry, business category, deal type, etc.

Start:
    .venv/bin/python server.py

First run opens a headless browser to log in. Subsequent runs reuse
session_state.json; the access token is refreshed via Python RSA on expiry.
"""

import asyncio
import json
import time
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

import auth

BASE_URL = "https://gfdata.sigmify.com"

app = Server("gfdata")

_session: dict | None = None
_client: httpx.AsyncClient | None = None


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_client(token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{BASE_URL}/gfdr/",
            "x-api-key": str(int(time.time() * 1000)),
        },
        timeout=30.0,
    )


async def _ensure_session() -> tuple[dict, httpx.AsyncClient]:
    global _session, _client
    if _session is None:
        _session = await auth.get_session()
        _client = _make_client(_session["access_token"])
    return _session, _client


async def _api_get(path: str, **kwargs) -> Any:
    session, client = await _ensure_session()
    resp = await client.get(path, **kwargs)
    if resp.status_code == 401:
        session = await auth.refresh_token(session)
        client.headers["Authorization"] = f"Bearer {session['access_token']}"
        resp = await client.get(path, **kwargs)
    resp.raise_for_status()
    return resp.json()


async def _api_post(path: str, body: dict) -> Any:
    session, client = await _ensure_session()
    client.headers["x-api-key"] = str(int(time.time() * 1000))
    resp = await client.post(path, json=body)
    if resp.status_code == 401:
        session = await auth.refresh_token(session)
        client.headers["Authorization"] = f"Bearer {session['access_token']}"
        resp = await client.post(path, json=body)
    resp.raise_for_status()
    return resp.json()


def _audit_fields(session: dict, report_code: str) -> dict:
    """Fields the server uses for audit logging — populated from user profile."""
    return {
        "company": session.get("tenant", ""),
        "location": session.get("location", ""),
        "cre_user": session.get("user_code", ""),
        "cre_date": "",
        "upd_date": "",
        "upd_user": session.get("user_code", ""),
        "type": "search",
        "ip_address": "",
        "report_code": report_code,
    }


def _base_filter(
    session: dict,
    report_code: str,
    business_categories: list[str] | None = None,
    naics_code: str = "",
    group_type: str = "Mean",
    frequency: str = "By Year",
    views: str = "Valuation",
    from_year: str = "",
    deal_type: list[str] | None = None,
    seller_type: list[str] | None = None,
    platform: list[str] | None = None,
    db_type: str = "standard",
) -> dict:
    return {
        "stNAICS_Code": naics_code,
        "naicsValue": naics_code,
        "stBusiness_Category": business_categories or ["All"],
        "groupType": group_type,
        "aboveAvg": "All",
        "platform": platform or ["All"],
        "trxType": deal_type or ["All"],
        "sellerType": seller_type or ["All"],
        "insurance": "All",
        "familyOffice": ["All"],
        "lenderType": ["All"],
        "frequency": frequency,
        "views": views,
        "customViewDataArray": [],
        "idCustomView": "",
        "yearViewMetric": "",
        "quarterViewMetric": "",
        "selectedDataElement": "",
        "dbType": db_type,
        "stYear": from_year,
        **_audit_fields(session, report_code),
    }


# ---------------------------------------------------------------------------
# MCP tool registry
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="query_comps_by_year",
            description=(
                "Query GF Data for aggregated M&A deal statistics grouped by year or quarter. "
                "Returns metrics like TEV/EBITDA, TEV/Revenue, EBITDA margin, deal count (N), "
                "etc. for the matching deal population. Use this to build comp tables or "
                "benchmark valuations over time. Filters: industry (NAICS), business category, "
                "deal type (PE / Corporate / All), seller type, deal-size segment."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter by GF Data business category. "
                            'Use list_business_categories to see options. Default: ["All"]. '
                            'Example: ["Business Services", "Health Care Services"]'
                        ),
                    },
                    "naics_code": {
                        "type": "string",
                        "description": (
                            "Filter by NAICS code. Use list_industries to look up codes. "
                            'Example: "5112" for software publishers.'
                        ),
                    },
                    "frequency": {
                        "type": "string",
                        "enum": ["By Year", "By Quarter"],
                        "description": "Group results by year (default) or quarter.",
                    },
                    "group_type": {
                        "type": "string",
                        "enum": ["Mean", "Median"],
                        "description": "Statistical aggregation — Mean (default) or Median.",
                    },
                    "from_year": {
                        "type": "string",
                        "description": 'Start year filter, e.g. "2020".',
                    },
                    "deal_type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            'Transaction type filter. Options: ["All"], ["PE"], ["Corporate"]. '
                            "PE = private equity / financial sponsor. Corporate = strategic."
                        ),
                    },
                    "seller_type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            'Seller type filter. Options include ["All"], ["PE"], ["Corporate"].'
                        ),
                    },
                    "db_type": {
                        "type": "string",
                        "enum": ["standard", "small"],
                        "description": (
                            '"standard" = full database (default). '
                            '"small" = smaller transactions sub-database.'
                        ),
                    },
                    "views": {
                        "type": "string",
                        "description": (
                            'Data view to return. Default "Valuation". '
                            "Use get_available_metrics to see other options."
                        ),
                    },
                },
            },
        ),
        types.Tool(
            name="query_comps_by_tev_range",
            description=(
                "Query GF Data for aggregated M&A deal statistics grouped by TEV (deal size) range. "
                "Each row represents a size bucket (e.g. $10-25M, $25-50M, $50-100M, etc.) "
                "with median/mean valuation multiples and deal count. "
                "Useful for understanding how valuation multiples vary by deal size."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "business_categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'GF Data business category filter. Default: ["All"].',
                    },
                    "naics_code": {
                        "type": "string",
                        "description": "NAICS code filter.",
                    },
                    "group_type": {
                        "type": "string",
                        "enum": ["Mean", "Median"],
                        "description": "Mean (default) or Median.",
                    },
                    "deal_type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'Transaction type: ["All"], ["PE"], ["Corporate"].',
                    },
                    "seller_type": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Seller type filter.",
                    },
                    "db_type": {
                        "type": "string",
                        "enum": ["standard", "small"],
                        "description": '"standard" (default) or "small" deals database.',
                    },
                    "views": {
                        "type": "string",
                        "description": 'Data view. Default "Valuation".',
                    },
                },
            },
        ),
        types.Tool(
            name="list_industries",
            description=(
                "Search GF Data NAICS industry codes. Returns a hierarchical list of "
                "industries matching the search term. Use the returned 'value' field as "
                "the naics_code parameter in query_comps_by_year / query_comps_by_tev_range."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": 'Industry name or NAICS code to search for. Use "" to list all top-level.',
                    },
                    "parent_item": {
                        "type": "string",
                        "description": 'Parent NAICS code to list children of. Default "all".',
                    },
                },
            },
        ),
        types.Tool(
            name="list_business_categories",
            description=(
                "Return the GF Data business categories with transaction counts. "
                "Use the returned category names as the business_categories filter "
                "in query_comps_by_year / query_comps_by_tev_range."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "db_type": {
                        "type": "string",
                        "enum": ["standard", "small"],
                        "description": '"standard" (default) or "small" deals database.',
                    },
                },
            },
        ),
        types.Tool(
            name="get_available_metrics",
            description=(
                "Return the data columns / metrics available in GF Data, "
                "along with their display labels and internal keys. "
                "These can be used to interpret query results or request custom views."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "query_comps_by_year":
            result = await _query_comps_by_year(arguments)
        elif name == "query_comps_by_tev_range":
            result = await _query_comps_by_tev_range(arguments)
        elif name == "list_industries":
            result = await _list_industries(arguments)
        elif name == "list_business_categories":
            result = await _list_business_categories(arguments)
        elif name == "get_available_metrics":
            result = await _get_available_metrics()
        else:
            raise ValueError(f"Unknown tool: {name}")
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as exc:
        return [types.TextContent(type="text", text=f"Error: {exc}")]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def _query_comps_by_year(args: dict) -> Any:
    session, _ = await _ensure_session()
    db = args.get("db_type", "standard")
    freq = args.get("frequency", "By Year")
    report_code = "by_quarter" if freq == "By Quarter" else "by_year"
    endpoint = f"/api/v1/searchableDB/{'small/' if db == 'small' else ''}byYear"

    body = _base_filter(
        session,
        report_code=report_code,
        business_categories=args.get("business_categories"),
        naics_code=args.get("naics_code", ""),
        group_type=args.get("group_type", "Mean"),
        frequency=freq,
        views=args.get("views", "Valuation"),
        from_year=args.get("from_year", ""),
        deal_type=args.get("deal_type"),
        seller_type=args.get("seller_type"),
        db_type=db,
    )

    # Fetch data + column headers in parallel
    data, headers = await asyncio.gather(
        _api_post(endpoint, body),
        _api_post(
            "/api/v1/searchableDB/byYearsRangeReportHeader",
            {"views": args.get("views", "Valuation"), "customViewDataArray": []},
        ),
    )
    return {"columns": headers, "rows": data}


async def _query_comps_by_tev_range(args: dict) -> Any:
    session, _ = await _ensure_session()
    db = args.get("db_type", "standard")
    body = _base_filter(
        session,
        report_code="tev_ranges",
        business_categories=args.get("business_categories"),
        naics_code=args.get("naics_code", ""),
        group_type=args.get("group_type", "Mean"),
        frequency="By Year",
        views=args.get("views", "Valuation"),
        deal_type=args.get("deal_type"),
        seller_type=args.get("seller_type"),
        db_type=db,
    )

    data, headers = await asyncio.gather(
        _api_post("/api/v1/searchableDB/tevRanges", body),
        _api_post(
            "/api/v1/searchableDB/tevRangeReportHeader",
            {
                "views": args.get("views", "Valuation"),
                "customViewDataArray": [],
                "fromYear": None,
                "toYear": None,
            },
        ),
    )
    return {"columns": headers, "rows": data}


async def _list_industries(args: dict) -> Any:
    term = args.get("search_term", "")
    parent = args.get("parent_item", "all" if term else "")
    return await _api_get(
        "/api/v1/searchableDB/naicsList",
        params={"searchTerm": term, "parentItem": parent},
    )


async def _list_business_categories(args: dict) -> Any:
    db = args.get("db_type", "standard")
    path = "/api/v1/searchableDB/small/businessCategoryList" if db == "small" else "/api/v1/searchableDB/businessCategoryList"
    return await _api_get(path)


async def _get_available_metrics() -> Any:
    return await _api_post("/api/v1/searchableDB/getCustomViewDataPoints", {})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
