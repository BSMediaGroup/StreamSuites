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
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv


# ==================================================
# Load environment
# ==================================================

ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=ROOT / ".env")


# ==================================================
# Config
# ==================================================

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_LOGIN_REDIRECT_URI = os.getenv("DISCORD_LOGIN_REDIRECT_URI")

SESSION_SECRET = os.getenv("STREAMSUITES_SESSION_SECRET")
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("STREAMSUITES_ADMIN_EMAILS", "").split(",")
    if e.strip()
}

CREATOR_RETURN = "https://creator.streamsuites.app/auth/success.html"
ADMIN_RETURN = "https://admin.streamsuites.app/auth/success.html"

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8787

if not all([
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_LOGIN_REDIRECT_URI,
    SESSION_SECRET
]):
    raise RuntimeError("Missing required environment variables")


# ==================================================
# Signing helpers
# ==================================================

def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def sign_blob(blob: bytes) -> str:
    return _b64u(hmac.new(SESSION_SECRET.encode(), blob, hashlib.sha256).digest())

def make_signed_value(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return _b64u(raw) + "." + sign_blob(raw)

def parse_signed_value(value: str) -> dict | None:
    try:
        raw_b64, sig = value.split(".", 1)
        raw = _b64u_dec(raw_b64)
        if not hmac.compare_digest(sig, sign_blob(raw)):
            return None
        return json.loads(raw)
    except Exception:
        return None


# ==================================================
# Cookie helpers
# ==================================================

def get_cookie(handler, name):
    cookie = handler.headers.get("Cookie")
    if not cookie:
        return None
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(name + "="):
            return part.split("=", 1)[1]
    return None

def set_cookie(handler, name, value, max_age=3600):
    handler.send_header(
        "Set-Cookie",
        f"{name}={value}; Max-Age={max_age}; HttpOnly; Secure; SameSite=Lax; Path=/"
    )


# ==================================================
# OAuth helpers
# ==================================================

def google_exchange(code):
    r = requests.post(
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
    r.raise_for_status()
    return r.json()

def google_profile(id_token):
    r = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def github_exchange(code):
    r = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": GITHUB_REDIRECT_URI,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def github_profile(token):
    r = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def github_emails(token):
    r = requests.get(
        "https://api.github.com/user/emails",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def discord_exchange(code):
    r = requests.post(
        "https://discord.com/api/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_LOGIN_REDIRECT_URI,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]

def discord_profile(token):
    r = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ==================================================
# HTTP Handler
# ==================================================

class AuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/auth/login/google":
            self.handle_login_google(qs)
            return

        if parsed.path == "/auth/login/github":
            self.handle_login_github(qs)
            return

        if parsed.path == "/auth/login/discord":
            self.handle_login_discord(qs)
            return

        if parsed.path == "/auth/callback/google":
            self.handle_google_callback(qs)
            return

        if parsed.path == "/auth/callback/github":
            self.handle_github_callback(qs)
            return

        if parsed.path == "/auth/discord/login/callback":
            self.handle_discord_callback(qs)
            return

        self.send_error(404)

    # --------------------------------------------------

    def _start_oauth(self, provider, surface, location, state):
        self.send_response(302)
        set_cookie(self, "ss_oauth_state", make_signed_value({
            "state": state,
            "surface": surface,
            "provider": provider,
            "iat": int(time.time())
        }), max_age=600)

        self.send_header("Location", location)
        self.end_headers()

    def _load_state(self, returned_state, provider):
        raw = get_cookie(self, "ss_oauth_state")
        data = parse_signed_value(raw or "")
        if not data or data.get("state") != returned_state or data.get("provider") != provider:
            raise ValueError("Invalid OAuth state")
        return data["surface"]

    def _finalize_login(self, email, name, provider, provider_id, surface, extra=None):
        role = "admin" if email and email in ADMIN_EMAILS else "creator"

        session = {
            "email": email,
            "name": name,
            "role": role,
            "tier": "OPEN",
            "provider": provider,
            "provider_id": provider_id,
            "iat": int(time.time())
        }

        if extra:
            session.update(extra)

        self.send_response(302)
        set_cookie(self, "streamsuites_session", make_signed_value(session), max_age=60 * 60 * 24 * 7)
        set_cookie(self, "ss_oauth_state", "deleted", max_age=0)

        self.send_header(
            "Location",
            ADMIN_RETURN if role == "admin" or surface == "admin" else CREATOR_RETURN
        )
        self.end_headers()

    # --------------------------------------------------

    def handle_login_google(self, qs):
        surface = qs.get("surface", ["creator"])[0]
        state = secrets.token_urlsafe(32)

        self._start_oauth(
            "google",
            surface,
            "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
                "client_id": GOOGLE_CLIENT_ID,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "response_type": "code",
                "scope": "openid email profile",
                "prompt": "select_account",
                "state": state,
            }),
            state
        )

    def handle_login_github(self, qs):
        surface = qs.get("surface", ["creator"])[0]
        state = secrets.token_urlsafe(32)

        self._start_oauth(
            "github",
            surface,
            "https://github.com/login/oauth/authorize?" + urlencode({
                "client_id": GITHUB_CLIENT_ID,
                "redirect_uri": GITHUB_REDIRECT_URI,
                "scope": "read:user user:email",
                "state": state,
            }),
            state
        )

    def handle_login_discord(self, qs):
        surface = qs.get("surface", ["creator"])[0]
        state = secrets.token_urlsafe(32)

        self._start_oauth(
            "discord",
            surface,
            "https://discord.com/oauth2/authorize?" + urlencode({
                "client_id": DISCORD_CLIENT_ID,
                "redirect_uri": DISCORD_LOGIN_REDIRECT_URI,
                "response_type": "code",
                "scope": "identify email",
                "prompt": "consent",
                "state": state,
            }),
            state
        )

    # --------------------------------------------------

    def handle_google_callback(self, qs):
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        surface = self._load_state(state, "google")

        tokens = google_exchange(code)
        profile = google_profile(tokens["id_token"])

        self._finalize_login(
            email=profile.get("email", "").lower(),
            name=profile.get("name", ""),
            provider="google",
            provider_id=profile["sub"],
            surface=surface
        )

    def handle_github_callback(self, qs):
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        surface = self._load_state(state, "github")

        token = github_exchange(code)
        user = github_profile(token)
        emails = github_emails(token)
        primary = next(e for e in emails if e["primary"] and e["verified"])

        self._finalize_login(
            email=primary["email"].lower(),
            name=user.get("name") or user.get("login"),
            provider="github",
            provider_id=str(user["id"]),
            surface=surface
        )

    def handle_discord_callback(self, qs):
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        surface = self._load_state(state, "discord")

        token = discord_exchange(code)
        user = discord_profile(token)

        self._finalize_login(
            email=(user.get("email") or "").lower() or None,
            name=user.get("username"),
            provider="discord",
            provider_id=user["id"],
            surface=surface,
            extra={
                "discord_id": user["id"],
                "discord_username": user["username"],
                "discord_verified": user.get("verified", False),
            }
        )


# ==================================================
# Run
# ==================================================

def run():
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), AuthHandler)
    print(f"StreamSuites Auth API running on {LISTEN_HOST}:{LISTEN_PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
