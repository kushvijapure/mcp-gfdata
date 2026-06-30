# GF Data MCP

An MCP server that connects [Claude Desktop](https://claude.ai/download) to [GF Data](https://gfdata.sigmify.com) — a professional M&A comps database with aggregated valuation multiples across thousands of private-company transactions.

Once installed, you can ask Claude things like:

> *"What are median TEV/EBITDA multiples for software companies over the last 5 years?"*
> *"Break down PE vs. strategic deal multiples by deal size for healthcare services."*
> *"Build a comp table for business services transactions, grouped by year."*

---

## What it does

GF Data publishes aggregated statistics on private-market M&A transactions — deal counts, TEV/EBITDA, TEV/Revenue, EBITDA margins, and more — sliced by industry, business category, deal type, seller type, and deal size. This server exposes that data as MCP tools so Claude can query it directly in conversation.

**Requires a GF Data subscription.** Sign up at [gfdata.sigmify.com](https://gfdata.sigmify.com).

---

## Prerequisites

- macOS (Claude Desktop only)
- Python 3.10 or higher
- An active GF Data account (email + password)
- [Claude Desktop](https://claude.ai/download)

---

## Installation

Clone the repo and run the setup script. It handles everything — virtualenv, dependencies, Playwright, credentials, and wiring up Claude Desktop.

```bash
git clone https://github.com/kushvijapure/mcp-gfdata.git
cd mcp-gfdata
bash setup.sh
```

The script will:

1. Detect (or install via Homebrew) Python 3.10+
2. Create a `.venv` and install all dependencies
3. Install Playwright's Chromium (used once for first-time login)
4. Prompt for your GF Data email and password, saved locally to `.env`
5. Run a headless login to verify credentials and cache your session
6. Automatically add the server to your Claude Desktop config

**Restart Claude Desktop** when the script finishes. You should see GF Data tools available in the tools menu.

---

## Available tools

| Tool | Description |
|---|---|
| `query_comps_by_year` | M&A deal stats (TEV/EBITDA, TEV/Rev, margins, deal count) grouped by year or quarter |
| `query_comps_by_tev_range` | Same stats grouped by deal size bucket ($10–25M, $25–50M, $50–100M, etc.) |
| `list_industries` | Search NAICS industry codes to use as filters |
| `list_business_categories` | List GF Data's business categories with transaction counts |
| `get_available_metrics` | Return all available data columns and their internal keys |

All tools share a consistent set of filters:

- **business_categories** — GF Data sector groupings (e.g. `"Business Services"`, `"Health Care Services"`)
- **naics_code** — standard NAICS industry code (use `list_industries` to look up)
- **deal_type** — `"PE"`, `"Corporate"`, or `"All"`
- **seller_type** — `"PE"`, `"Corporate"`, or `"All"`
- **group_type** — `"Mean"` or `"Median"`
- **db_type** — `"standard"` (full database) or `"small"` (smaller transactions sub-database)

---

## Example prompts

```
What are mean TEV/EBITDA multiples for software (NAICS 5112) by year since 2018?
```

```
Compare PE vs. corporate acquirer multiples for healthcare services, grouped by deal size.
```

```
Show me median valuation multiples for business services transactions in the small-deal database.
```

```
What business categories have the most transactions in GF Data?
```

---

## How authentication works

The server uses a two-phase auth flow:

1. **First run** — a headless Chromium browser logs into GF Data and captures the access token + user profile, saved to `session_state.json`
2. **Subsequent runs** — the cached session is reused; if the token expires, it's silently refreshed using Python RSA (no browser needed)

Your credentials stay on your machine in `.env` and are never transmitted anywhere except directly to GF Data's login endpoint.

---

## Troubleshooting

**"Login failed — no accessToken captured"**
Double-check your credentials in `.env`. Make sure your GF Data subscription is active.

**Claude Desktop doesn't show the tools**
Confirm `~/gfdata-mcp/session_state.json` exists (created after a successful login), then fully quit and reopen Claude Desktop.

**Token expired errors mid-session**
The server auto-refreshes tokens on 401 responses. If it keeps failing, delete `session_state.json` and restart — this triggers a fresh headless login.

**Python not found**
Install Python 3.10+ via [Homebrew](https://brew.sh): `brew install python@3.12`

---

## Project structure

```
gfdata-mcp/
├── server.py          # MCP server + tool definitions
├── auth.py            # Auth flow (RSA login + session management)
├── requirements.txt   # Python dependencies
├── setup.sh           # One-command installer
└── .env.example       # Credential template
```

---

## Dependencies

- [mcp](https://github.com/anthropics/mcp) — MCP server framework
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [playwright](https://playwright.dev/python/) — headless browser for first-time login
- [cryptography](https://cryptography.io/) — RSA encryption for the auth handshake
- [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` loading
