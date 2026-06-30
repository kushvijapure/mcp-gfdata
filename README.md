# GF Data MCP Server

<p align="left">
  <a href="https://www.python.org/downloads/" target="_blank"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="https://github.com/kushvijapure/mcp-gfdata/blob/main/LICENSE" target="_blank"><img src="https://img.shields.io/badge/License-MIT-green" alt="License"></a>
  <a href="https://gfdata.sigmify.com" target="_blank"><img src="https://img.shields.io/badge/Data-GF%20Data-orange" alt="GF Data"></a>
</p>

Connects [Claude Desktop](https://claude.ai/download) to [GF Data](https://gfdata.sigmify.com) — a professional M&A comps database with aggregated valuation multiples across thousands of private-company transactions.

Ask Claude things like:

> *"What are median TEV/EBITDA multiples for software companies over the last 5 years?"*
> *"Break down PE vs. strategic deal multiples by deal size for healthcare services."*
> *"Build a comp table for business services transactions grouped by year."*

> [!IMPORTANT]
> **Requires an active GF Data subscription.** Sign up at [gfdata.sigmify.com](https://gfdata.sigmify.com).

---

## Tools

| Tool | Description | Status |
|------|-------------|--------|
| `query_comps_by_year` | M&A deal stats (TEV/EBITDA, TEV/Revenue, EBITDA margin, deal count) grouped by year or quarter | working |
| `query_comps_by_tev_range` | Same stats grouped by deal size bucket ($10–25M, $25–50M, $50–100M, etc.) | working |
| `list_industries` | Search NAICS industry codes to use as filters in comp queries | working |
| `list_business_categories` | List GF Data's business categories with transaction counts | working |
| `get_available_metrics` | Return all available data columns and their internal keys | working |

---

## 🚀 Setup

**Prerequisites:** macOS, Python 3.10+, [Claude Desktop](https://claude.ai/download), and a GF Data account.

```bash
git clone https://github.com/kushvijapure/mcp-gfdata.git
cd mcp-gfdata
bash setup.sh
```

The script handles everything:

1. Detects (or installs via Homebrew) Python 3.10+
2. Creates a `.venv` and installs all dependencies
3. Installs Playwright's Chromium — used once for first-time login
4. Prompts for your GF Data email and password, saved locally to `.env`
5. Runs a headless login to verify credentials and cache your session
6. Automatically writes the server config into Claude Desktop

**Restart Claude Desktop** when the script finishes. GF Data tools will appear in the tools menu.

### Claude Desktop config

If you'd rather configure manually, add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gfdata": {
      "command": "/Users/yourname/gfdata-mcp/.venv/bin/python",
      "args": ["/Users/yourname/gfdata-mcp/server.py"],
      "env": {
        "GFDATA_EMAIL": "your@email.com",
        "GFDATA_PASSWORD": "yourpassword"
      }
    }
  }
}
```

<details>
<summary><b>🔧 Filters reference</b></summary>

All query tools share a common set of optional filters:

| Filter | Type | Options | Default |
|--------|------|---------|---------|
| `business_categories` | `string[]` | Use `list_business_categories` to see options | `["All"]` |
| `naics_code` | `string` | Use `list_industries` to look up codes | `""` |
| `deal_type` | `string[]` | `["All"]`, `["PE"]`, `["Corporate"]` | `["All"]` |
| `seller_type` | `string[]` | `["All"]`, `["PE"]`, `["Corporate"]` | `["All"]` |
| `group_type` | `string` | `"Mean"`, `"Median"` | `"Mean"` |
| `frequency` | `string` | `"By Year"`, `"By Quarter"` | `"By Year"` |
| `from_year` | `string` | e.g. `"2020"` | `""` |
| `db_type` | `string` | `"standard"`, `"small"` | `"standard"` |
| `views` | `string` | Use `get_available_metrics` to see options | `"Valuation"` |

</details>

<details>
<summary><b>❗ Troubleshooting</b></summary>

**"Login failed — no accessToken captured"**
Double-check your credentials in `.env`. Make sure your GF Data subscription is active and you can log in at [gfdata.sigmify.com](https://gfdata.sigmify.com).

**Claude Desktop doesn't show GF Data tools**
Confirm `~/gfdata-mcp/session_state.json` exists — it's created after a successful login. Then fully quit (`Cmd+Q`) and reopen Claude Desktop.

**Token expired errors mid-session**
The server auto-refreshes tokens on 401 responses. If it keeps failing, delete `session_state.json` and restart — this triggers a fresh headless login.

**Python not found**
Install Python 3.10+ via [Homebrew](https://brew.sh):
```bash
brew install python@3.12
```

**Git identity warning on `git push`**
This is cosmetic. Fix it with:
```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

</details>

---

## 🔐 How authentication works

The server uses a two-phase auth flow so you only need the browser once:

1. **First run** — a headless Chromium browser logs into GF Data, captures the access token and user profile, and saves everything to `session_state.json`
2. **Subsequent runs** — the cached session is reused. If the token expires mid-session, it's silently refreshed using Python RSA — no browser required

Your credentials stay on your machine in `.env` and are only sent directly to GF Data's login endpoint. `session_state.json` and `.env` are both `.gitignore`d.

---

## 📁 Project structure

```
gfdata-mcp/
├── server.py          # MCP server — tool definitions and API calls
├── auth.py            # Auth flow — RSA login and session management
├── requirements.txt   # Python dependencies
├── setup.sh           # One-command installer
└── .env.example       # Credential template
```

---

## Dependencies

- [mcp](https://github.com/anthropics/mcp) — MCP server framework
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [playwright](https://playwright.dev/python/) — headless browser for first-time login
- [cryptography](https://cryptography.io/) — RSA encryption for the GF Data auth handshake
- [python-dotenv](https://github.com/theskumar/python-dotenv) — `.env` file loading
