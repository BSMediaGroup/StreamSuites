from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs, quote

import requests
from dotenv import load_dotenv


# --------------------------------------------------
# Load .env (ALWAYS from this script's folder)
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=ROOT / ".env")


# --------------------------------------------------
# Config
# --------------------------------------------------

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

SESSION_SECRET = os.getenv("STREAMSUITES_SESSION_SECRET")
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("STREAMSUITES_ADMIN_EMAILS", "").split(",")
    if e.strip()
}

# Where users land after auth
CREATOR_RETURN = "https://creator.streamsuites.app/auth/success.html"
ADMIN_RETURN = "https://admin.streamsuites.app/auth/success.html"

# Local listen port (must match your cloudflared config)
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8787

if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, SESSION_SECRET]):
    raise RuntimeError(
        "Missing required env vars: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, STREAMSUITES_SESSION_SECRET"
    )


# --------------------------------------------------
# Signing helpers
# --------------------------------------------------

def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64u_dec(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def sign_blob(blob: bytes) -> str:
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), blob, hashlib.sha256).digest()
    return _b64u(sig)

def make_signed_value(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = sign_blob(raw)
    return _b64u(raw) + "." + sig

def parse_signed_value(value: str) -> dict | None:
    try:
        raw_b64, sig = value.split(".", 1)
        raw = _b64u_dec(raw_b64)
        expected = sign_blob(raw)
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


# --------------------------------------------------
# Cookie helpers
# --------------------------------------------------

def get_cookie(handler: BaseHTTPRequestHandler, name: str) -> str | None:
    cookie = handler.headers.get("Cookie")
    if not cookie:
        return None
    parts = [p.strip() for p in cookie.split(";")]
    for p in parts:
        if p.startswith(name + "="):
            return p.split("=", 1)[1]
    return None

def set_cookie(handler: BaseHTTPRequestHandler, name: str, value: str, *, max_age: int = 3600) -> None:
    # Secure cookie: works on https api domain via Cloudflare
    handler.send_header(
        "Set-Cookie",
        f"{name}={value}; Max-Age={max_age}; HttpOnly; Secure; SameSite=Lax; Path=/",
    )


def redirect(handler: BaseHTTPRequestHandler, location: str) -> None:
    handler.send_response(302)
    handler.send_header("Location", location)
    handler.end_headers()


# --------------------------------------------------
# OAuth helpers
# --------------------------------------------------

def google_exchange_code(code: str) -> dict:
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": GOOGLE_REDIRECT_URI,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()

def google_tokeninfo(id_token: str) -> dict:
    # Quick validation (issuer/audience/expiry/signature handled by Google)
    resp = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------
# HTTP Handler
# --------------------------------------------------

class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)

            # Health check
            if parsed.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","service":"streamsuites-auth"}')
                return

            # ------------------------------------------
            # /auth/login/google
            # ------------------------------------------
            if parsed.path == "/auth/login/google":
                # Optional surface hint, so we can redirect to creator/admin UI correctly
                qs = parse_qs(parsed.query)
                surface = (qs.get("surface", ["creator"])[0] or "creator").lower()
                if surface not in ("creator", "admin"):
                    surface = "creator"

                state = secrets.token_urlsafe(32)

                # Store state in a signed cookie (prevents CSRF)
                state_cookie = make_signed_value({
                    "state": state,
                    "surface": surface,
                    "iat": int(time.time())
                })

                self.send_response(302)
                set_cookie(self, "ss_oauth_state", state_cookie, max_age=600)

                params = {
                    "client_id": GOOGLE_CLIENT_ID,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "response_type": "code",
                    "scope": "openid email profile",
                    "state": state,
                    "access_type": "online",
                    "prompt": "select_account",
                }

                url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
                self.send_header("Location", url)
                self.end_headers()
                return

            # ------------------------------------------
            # /auth/callback/google
            # ------------------------------------------
            if parsed.path == "/auth/callback/google":
                qs = parse_qs(parsed.query)
                code = qs.get("code", [None])[0]
                returned_state = qs.get("state", [None])[0]

                if not code or not returned_state:
                    self.send_error(400, "Missing code or state")
                    return

                state_cookie_raw = get_cookie(self, "ss_oauth_state")
                if not state_cookie_raw:
                    self.send_error(400, "Missing state cookie")
                    return

                state_payload = parse_signed_value(state_cookie_raw)
                if not state_payload:
                    self.send_error(400, "Invalid state cookie")
                    return

                if state_payload.get("state") != returned_state:
                    self.send_error(400, "State mismatch")
                    return

                surface = state_payload.get("surface", "creator")

                tokens = google_exchange_code(code)
                id_token = tokens.get("id_token")
                if not id_token:
                    self.send_error(500, "Missing id_token from Google")
                    return

                profile = google_tokeninfo(id_token)

                email = (profile.get("email") or "").lower()
                sub = profile.get("sub")
                name = profile.get("name") or ""

                if not email or not sub:
                    self.send_error(500, "Google profile missing email/sub")
                    return

                role = "admin" if email in ADMIN_EMAILS else "creator"

                # Create signed StreamSuites session cookie (no DB yet)
                session = make_signed_value({
                    "email": email,
                    "name": name,
                    "role": role,
                    "tier": "OPEN",
                    "provider": "google",
                    "provider_id": sub,
                    "iat": int(time.time())
                })

                self.send_response(302)
                set_cookie(self, "streamsuites_session", session, max_age=60 * 60 * 24 * 7)

                # Clear oauth state cookie
                set_cookie(self, "ss_oauth_state", "deleted", max_age=0)

                # Redirect to the correct surface success page
                if role == "admin" or surface == "admin":
                    self.send_header("Location", ADMIN_RETURN)
                else:
                    self.send_header("Location", CREATOR_RETURN)
                self.end_headers()
                return

            self.send_error(404)

        except requests.HTTPError as e:
            # Return readable errors instead of crashing/EOF
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = {"error": "HTTPError", "details": str(e)}
            self.wfile.write(json.dumps(body).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            body = {"error": "ServerError", "details": str(e)}
            self.wfile.write(json.dumps(body).encode("utf-8"))


def run():
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), AuthHandler)
    print(f"StreamSuites Auth API running on http://{LISTEN_HOST}:{LISTEN_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
