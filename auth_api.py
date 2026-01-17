from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import boto3
import requests
from dotenv import load_dotenv


# ==================================================
# Paths / Environment
# ==================================================

ROOT = Path(__file__).resolve().parent

# StreamSuites/runtime/data/accounts.db
RUNTIME_DIR = ROOT / "runtime" / "data"
DB_PATH = RUNTIME_DIR / "accounts.db"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(dotenv_path=ROOT / ".env")


# ==================================================
# Config
# ==================================================

AWS_REGION = os.getenv("AWS_REGION")
SES_FROM = os.getenv("SES_FROM_ADDRESS")

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

# Explicit checks (fail fast)
_required = [
    SESSION_SECRET,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_REDIRECT_URI,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_LOGIN_REDIRECT_URI,
    AWS_REGION, SES_FROM,
    os.getenv("AWS_ACCESS_KEY_ID"), os.getenv("AWS_SECRET_ACCESS_KEY"),
]
if not all(_required):
    raise RuntimeError("Missing required environment variables in .env")


# ==================================================
# AWS SES
# ==================================================

ses = boto3.client(
    "ses",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)


# ==================================================
# Database
# ==================================================

def db():
    # NOTE: check_same_thread=False isn’t necessary with http.server single-threaded default,
    # but safe if you later swap server class.
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as conn:
        c = conn.cursor()

        # Accounts table (one row per email)
        c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            role TEXT,
            tier TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
        """)

        # Linked providers for an account (multiple per email)
        c.execute("""
        CREATE TABLE IF NOT EXISTS account_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            provider TEXT,
            provider_id TEXT,
            linked_at INTEGER,
            UNIQUE(email, provider),
            UNIQUE(provider, provider_id)
        )
        """)

        # Email magic-link tokens
        c.execute("""
        CREATE TABLE IF NOT EXISTS email_tokens (
            token TEXT PRIMARY KEY,
            email TEXT,
            expires_at INTEGER
        )
        """)

        conn.commit()

init_db()


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
# Account helpers (SQLite)
# ==================================================

def upsert_account(email: str, name: str | None, provider: str, provider_id: str, surface: str, extra: dict | None = None) -> dict:
    """
    - Ensures an account exists for this email
    - Links provider -> provider_id
    - Determines role (admin vs creator)
    - Returns session payload (dict) to be signed into cookie
    """
    now = int(time.time())
    email_l = (email or "").lower().strip()

    # role is determined by email membership in ADMIN_EMAILS
    role = "admin" if (email_l and email_l in ADMIN_EMAILS) else "creator"
    tier = "OPEN"

    # Default display name
    display_name = (name or "").strip() or (email_l.split("@")[0] if email_l else "")

    with db() as conn:
        c = conn.cursor()

        # Upsert accounts row
        c.execute("SELECT id, name FROM accounts WHERE email=?", (email_l,))
        row = c.fetchone()
        if row:
            c.execute(
                "UPDATE accounts SET name=?, role=?, tier=?, updated_at=? WHERE email=?",
                (display_name, role, tier, now, email_l),
            )
        else:
            c.execute(
                "INSERT INTO accounts (email, name, role, tier, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (email_l, display_name, role, tier, now, now),
            )

        # Link provider
        # If provider/provider_id is already linked elsewhere, UNIQUE(provider, provider_id) will enforce it.
        c.execute(
            "INSERT OR REPLACE INTO account_links (email, provider, provider_id, linked_at) VALUES (?,?,?,?)",
            (email_l, provider, str(provider_id), now),
        )

        conn.commit()

    session = {
        "email": email_l,
        "name": display_name,
        "role": role,
        "tier": tier,
        "provider": provider,
        "provider_id": str(provider_id),
        "iat": now,
    }

    if extra:
        # Keep it bounded to JSON-serializable primitives
        session.update(extra)

    # Surface preference still influences redirect (but role/admin always wins)
    session["surface"] = surface

    return session


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
# Email magic-link (SES)
# ==================================================

def send_magic_link(email: str, token: str):
    link = f"https://api.streamsuites.app/auth/verify/email?token={token}"

    ses.send_email(
        Source=SES_FROM,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": "Your StreamSuites login link", "Charset": "UTF-8"},
            "Body": {
                "Text": {
                    "Data": f"Click to sign in:\n\n{link}\n\nThis link expires in 15 minutes.",
                    "Charset": "UTF-8",
                }
            },
        },
    )


# ==================================================
# HTTP Handler
# ==================================================

class AuthHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/auth/signup/email":
            self.handle_email_signup()
            return

        self.send_error(404)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # -----------------------------
        # OAuth login endpoints
        # -----------------------------
        if parsed.path == "/auth/login/google":
            self.handle_login_google(qs)
            return

        if parsed.path == "/auth/login/github":
            self.handle_login_github(qs)
            return

        if parsed.path == "/auth/login/discord":
            self.handle_login_discord(qs)
            return

        # -----------------------------
        # OAuth callback endpoints
        # -----------------------------
        if parsed.path == "/auth/callback/google":
            self.handle_google_callback(qs)
            return

        if parsed.path == "/auth/callback/github":
            self.handle_github_callback(qs)
            return

        if parsed.path == "/auth/discord/login/callback":
            self.handle_discord_callback(qs)
            return

        # -----------------------------
        # Magic-link verification
        # -----------------------------
        if parsed.path == "/auth/verify/email":
            self.handle_email_verify(qs)
            return

        self.send_error(404)

    # --------------------------------------------------
    # OAuth state start / load
    # --------------------------------------------------

    def _start_oauth(self, provider, surface, location, state):
        self.send_response(302)
        set_cookie(self, "ss_oauth_state", make_signed_value({
            "state": state,
            "surface": surface,
            "provider": provider,
            "iat": int(time.time()),
        }), max_age=600)

        self.send_header("Location", location)
        self.end_headers()

    def _load_state(self, returned_state, provider):
        raw = get_cookie(self, "ss_oauth_state")
        data = parse_signed_value(raw or "")
        if not data or data.get("state") != returned_state or data.get("provider") != provider:
            raise ValueError("Invalid OAuth state")
        return data["surface"]

    def _finalize_login(self, session: dict):
        # session is a dict; we sign it into cookie
        role = session.get("role") or "creator"
        surface = session.get("surface") or "creator"

        self.send_response(302)
        set_cookie(self, "streamsuites_session", make_signed_value(session), max_age=60 * 60 * 24 * 7)
        set_cookie(self, "ss_oauth_state", "deleted", max_age=0)

        # Admin always wins, but surface can force admin UI for testing
        target = ADMIN_RETURN if role == "admin" or surface == "admin" else CREATOR_RETURN

        self.send_header("Location", target)
        self.end_headers()

    # --------------------------------------------------
    # OAuth: login endpoints
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
            state,
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
            state,
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
            state,
        )

    # --------------------------------------------------
    # OAuth: callback endpoints
    # --------------------------------------------------

    def handle_google_callback(self, qs):
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        if not code or not state:
            self.send_error(400, "Missing code/state")
            return

        surface = self._load_state(state, "google")

        tokens = google_exchange(code)
        profile = google_profile(tokens["id_token"])

        email = (profile.get("email") or "").lower().strip()
        if not email:
            self.send_error(500, "Google profile missing email")
            return

        session = upsert_account(
            email=email,
            name=profile.get("name", ""),
            provider="google",
            provider_id=profile.get("sub", ""),
            surface=surface,
        )

        self._finalize_login(session)

    def handle_github_callback(self, qs):
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        if not code or not state:
            self.send_error(400, "Missing code/state")
            return

        surface = self._load_state(state, "github")

        token = github_exchange(code)
        user = github_profile(token)
        emails = github_emails(token)

        # pick primary verified; fallback to first verified; then fail
        primary = None
        for e in emails:
            if e.get("primary") and e.get("verified"):
                primary = e
                break
        if not primary:
            for e in emails:
                if e.get("verified"):
                    primary = e
                    break
        if not primary:
            self.send_error(500, "No verified GitHub email available")
            return

        email = (primary.get("email") or "").lower().strip()
        if not email:
            self.send_error(500, "GitHub email missing")
            return

        session = upsert_account(
            email=email,
            name=user.get("name") or user.get("login") or "",
            provider="github",
            provider_id=str(user.get("id", "")),
            surface=surface,
        )

        self._finalize_login(session)

    def handle_discord_callback(self, qs):
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        if not code or not state:
            self.send_error(400, "Missing code/state")
            return

        surface = self._load_state(state, "discord")

        token = discord_exchange(code)
        user = discord_profile(token)

        email = ((user.get("email") or "").lower().strip()) or None
        username = user.get("username") or ""
        discord_id = user.get("id") or ""

        # Discord email can be missing if the user doesn’t have/allow it; if missing, we cannot create account row.
        # In that case, treat as error for standalone auth because we need an email identity.
        if not email:
            self.send_error(400, "Discord did not provide an email (required for standalone login)")
            return

        session = upsert_account(
            email=email,
            name=username,
            provider="discord",
            provider_id=str(discord_id),
            surface=surface,
            extra={
                "discord_id": str(discord_id),
                "discord_username": username,
                "discord_verified": bool(user.get("verified", False)),
            },
        )

        self._finalize_login(session)

    # --------------------------------------------------
    # Email: magic-link signup/login
    # --------------------------------------------------

    def handle_email_signup(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            self.send_error(400, "Missing body")
            return

        try:
            data = json.loads(self.rfile.read(length))
        except Exception:
            self.send_error(400, "Invalid JSON")
            return

        email = (data.get("email", "") or "").lower().strip()
        surface = (data.get("surface", "creator") or "creator").strip()

        if not email:
            self.send_error(400, "Missing email")
            return

        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + 900  # 15 minutes

        with db() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO email_tokens (token, email, expires_at) VALUES (?,?,?)",
                (token, email, expires),
            )
            conn.commit()

        # Note: surface is carried via token record? We keep it simple:
        # surface is re-derived from query param at verify time if present.
        # For now we store surface in a signed cookie so verification has it.
        self.send_response(204)
        set_cookie(self, "ss_email_surface", make_signed_value({
            "surface": surface,
            "iat": int(time.time()),
        }), max_age=900)
        self.end_headers()

        # Send email AFTER responding to reduce perceived latency.
        # (If SES fails, user can retry.)
        try:
            send_magic_link(email, token)
        except Exception:
            # Nothing else we can do; user will retry.
            pass

    def handle_email_verify(self, qs):
        token = qs.get("token", [None])[0]
        if not token:
            self.send_error(400, "Missing token")
            return

        now = int(time.time())

        with db() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT email, expires_at FROM email_tokens WHERE token=?",
                (token,),
            )
            row = c.fetchone()

            if not row:
                self.send_error(400, "Invalid token")
                return

            email, expires_at = row[0], int(row[1])
            if expires_at <= now:
                # expired
                c.execute("DELETE FROM email_tokens WHERE token=?", (token,))
                conn.commit()
                self.send_error(400, "Token expired")
                return

            # consume token
            c.execute("DELETE FROM email_tokens WHERE token=?", (token,))
            conn.commit()

        # surface from cookie (optional)
        surface = "creator"
        raw_surface = get_cookie(self, "ss_email_surface")
        sdata = parse_signed_value(raw_surface or "")
        if sdata and isinstance(sdata, dict) and sdata.get("surface") in ("creator", "admin"):
            surface = sdata["surface"]

        session = upsert_account(
            email=email,
            name=email.split("@")[0],
            provider="email",
            provider_id=email,
            surface=surface,
        )

        self.send_response(302)
        set_cookie(self, "streamsuites_session", make_signed_value(session), max_age=60 * 60 * 24 * 7)
        set_cookie(self, "ss_email_surface", "deleted", max_age=0)

        target = ADMIN_RETURN if session.get("role") == "admin" or surface == "admin" else CREATOR_RETURN
        self.send_header("Location", target)
        self.end_headers()


# ==================================================
# Run
# ==================================================

def run():
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), AuthHandler)
    print(f"StreamSuites Auth API running on {LISTEN_HOST}:{LISTEN_PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
