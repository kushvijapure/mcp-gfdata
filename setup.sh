#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/gfdata-mcp"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo "=== GF Data MCP Setup ==="
echo ""

# ── 1. Python 3.10+ check ──────────────────────────────────────────────────
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cmd" &>/dev/null; then
    ver=$("$cmd" -c 'import sys; print(sys.version_info[:2])')
    if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Python 3.10+ not found. Installing via Homebrew..."
  if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew not found. Install it from https://brew.sh then re-run this script."
    exit 1
  fi
  brew install python@3.12
  PYTHON=python3.12
fi

echo "Using Python: $PYTHON ($($PYTHON --version))"
echo ""

# ── 2. Copy files to ~/gfdata-mcp ─────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
  echo "Installing to $INSTALL_DIR ..."
  mkdir -p "$INSTALL_DIR"
  cp "$SCRIPT_DIR/server.py" "$SCRIPT_DIR/auth.py" "$SCRIPT_DIR/requirements.txt" \
     "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/"
else
  echo "Already in $INSTALL_DIR, skipping copy."
fi
cd "$INSTALL_DIR"

# ── 3. Virtual environment ─────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv .venv
fi
echo "Installing Python dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# ── 4. Playwright browsers ────────────────────────────────────────────────
echo "Installing Playwright Chromium (used for first-time login only)..."
.venv/bin/playwright install chromium --quiet

# ── 5. Credentials ────────────────────────────────────────────────────────
echo ""
if [ ! -f .env ]; then
  read -rp "GF Data email: " gf_email
  read -rsp "GF Data password: " gf_pass
  echo ""
  printf "GFDATA_EMAIL=%s\nGFDATA_PASSWORD=%s\n" "$gf_email" "$gf_pass" > .env
  echo "Credentials saved to .env"
else
  echo ".env already exists — skipping credential prompt."
fi

# ── 6. Test login ─────────────────────────────────────────────────────────
echo ""
echo "Testing login (opens headless browser, may take ~10s)..."
.venv/bin/python3 -c "
import asyncio, auth
async def t():
    s = await auth.get_session()
    print('  Login OK — user:', s.get('user_code'), '| tenant:', s.get('tenant'))
asyncio.run(t())
"

# ── 7. Claude Desktop config ──────────────────────────────────────────────
PYTHON_BIN="$INSTALL_DIR/.venv/bin/python"
SERVER_PATH="$INSTALL_DIR/server.py"

GF_EMAIL=$(grep GFDATA_EMAIL .env | cut -d= -f2-)
GF_PASS=$(grep GFDATA_PASSWORD .env | cut -d= -f2-)

echo ""
if [ -f "$CLAUDE_CONFIG" ]; then
  python3 -c "
import json, pathlib
p = pathlib.Path('$CLAUDE_CONFIG')
cfg = json.loads(p.read_text())
cfg.setdefault('mcpServers', {})['gfdata'] = {
    'command': '$PYTHON_BIN',
    'args': ['$SERVER_PATH'],
    'env': {'GFDATA_EMAIL': '$GF_EMAIL', 'GFDATA_PASSWORD': '$GF_PASS'}
}
p.write_text(json.dumps(cfg, indent=2))
print('  Claude Desktop config updated.')
"
else
  echo "  Claude Desktop config not found — writing snippet to gfdata_claude_config.json"
  python3 -c "
import json
snippet = {
  'mcpServers': {
    'gfdata': {
      'command': '$PYTHON_BIN',
      'args': ['$SERVER_PATH'],
      'env': {'GFDATA_EMAIL': '$GF_EMAIL', 'GFDATA_PASSWORD': '$GF_PASS'}
    }
  }
}
print(json.dumps(snippet, indent=2))
" > gfdata_claude_config.json
  echo "  Merge gfdata_claude_config.json into your Claude Desktop config manually."
fi

echo ""
echo "=== Setup complete. Restart Claude Desktop to activate GF Data tools. ==="
