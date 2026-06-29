"""
GF Data authentication module.

Login flow:
  1. GET /ws/loginService/getPublicKey  → 2048-bit RSA public key (DER, base64)
  2. RSA-PKCS1v15 encrypt email + password with that key
  3. POST /api/v1/auth/generateToken    → { accessToken, refreshToken }
  4. GET /ws/streamService/initAppData  → user profile (via Playwright, first run only)

Subsequent starts: load cached session_state.json; re-call generateToken on 401.
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

BASE_URL = "https://gfdata.sigmify.com"
SESSION_FILE = Path(__file__).parent / "session_state.json"

EMAIL = os.environ["GFDATA_EMAIL"]
PASSWORD = os.environ["GFDATA_PASSWORD"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE_URL}/gfdr/",
}


# ---------------------------------------------------------------------------
# RSA helpers
# ---------------------------------------------------------------------------

def _get_public_key_pem() -> bytes:
    raw = httpx.get(f"{BASE_URL}/ws/loginService/getPublicKey", timeout=10).text.strip()
    return base64.b64decode(raw)


def _rsa_encrypt(plaintext: str) -> str:
    der = _get_public_key_pem()
    pub = serialization.load_der_public_key(der)
    ct = pub.encrypt(plaintext.encode(), asym_padding.PKCS1v15())
    return base64.b64encode(ct).decode()


# ---------------------------------------------------------------------------
# Pure-Python token generation (no browser needed after first login)
# ---------------------------------------------------------------------------

async def _generate_token_python() -> str:
    enc_user = _rsa_encrypt(EMAIL)
    enc_pass = _rsa_encrypt(PASSWORD)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        resp = await client.post(
            "/api/v1/auth/generateToken",
            json={"username": enc_user, "password": enc_pass},
            headers={**_HEADERS, "x-api-key": str(int(time.time() * 1000))},
        )
        resp.raise_for_status()
        return resp.json()["accessToken"]


# ---------------------------------------------------------------------------
# First-time headless login via Playwright (also captures user profile)
# ---------------------------------------------------------------------------

async def _headless_login() -> dict:
    """Log in headlessly, return session dict with token + profile."""
    session: dict = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        async def handle_response(response):
            if "generateToken" in response.url:
                try:
                    body = await response.json()
                    session["access_token"] = body.get("accessToken", "")
                    session["refresh_token"] = body.get("refreshToken", "")
                except Exception:
                    pass
            elif "initAppData" in response.url:
                try:
                    body = await response.json()
                    session["user_code"] = body.get("loggedInUserCode", "")
                    session["tenant"] = body.get("loggedInuserTenant", "")
                    session["location"] = body.get("loggedInuserTenantLocation", "")
                except Exception:
                    pass

        page.on("response", handle_response)
        await page.goto(f"{BASE_URL}/signin.html")
        await page.wait_for_load_state("domcontentloaded")

        await page.fill("input[name='fld_2']", EMAIL)
        await page.fill("input[name='fld_3']", PASSWORD)
        await page.click("input[name='button']")

        # Wait for post-login API calls to complete
        try:
            await page.wait_for_url("**/gfdr/**", timeout=20_000)
        except Exception:
            pass
        await asyncio.sleep(3)

        await browser.close()

    if not session.get("access_token"):
        raise RuntimeError("Login failed — no accessToken captured. Check credentials in .env")
    return session


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_session() -> dict | None:
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except Exception:
            pass
    return None


def save_session(session: dict) -> None:
    SESSION_FILE.write_text(json.dumps(session, indent=2))


async def get_session() -> dict:
    """Return a valid session, logging in if needed."""
    cached = load_session()
    if cached and cached.get("access_token") and cached.get("user_code"):
        return cached

    print("No cached session — logging in via headless browser…", flush=True)
    session = await _headless_login()
    save_session(session)
    return session


async def refresh_token(session: dict) -> dict:
    """Re-generate the access token using Python RSA (no browser)."""
    print("Refreshing access token…", flush=True)
    session["access_token"] = await _generate_token_python()
    save_session(session)
    return session
