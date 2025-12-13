import uuid
from typing import List, Dict, Optional, Tuple

import httpx

from shared.logging.logger import get_logger

log = get_logger("rumble.chat_client")


class RumbleChatClient:
    """
    Direct REST client for Rumble chat.
    Auth is cookie-based ONLY.

    NOTE:
    - POST endpoint confirmed working:
        https://web7.rumble.com/chat/api/chat/{channel_id}/message
    - GET endpoint is NOT reliably:
        .../{channel_id}/messages   (often 404 HTML)
      So we auto-discover a working poll endpoint.
    """

    # We try a few web hosts because Rumble shards chat across webN.
    HOSTS = [
        "web7.rumble.com",
        "web6.rumble.com",
        "web8.rumble.com",
        "web5.rumble.com",
        "web4.rumble.com",
        "web3.rumble.com",
        "web2.rumble.com",
        "web1.rumble.com",
    ]

    PATH_CANDIDATES = [
        # Most common guesses (some are valid only on certain shards)
        "/chat/api/chat/{cid}/messages",
        "/chat/api/chat/{cid}/message",          # sometimes GET returns list / status on some backends
        "/chat/api/chat/{cid}/history",
        "/chat/api/chat/{cid}/poll",
        "/chat/api/chat/{cid}",
    ]

    def __init__(self, cookies: Dict[str, str], preferred_host: Optional[str] = None):
        self.cookies = cookies

        self._preferred_host = preferred_host  # optional override
        self._resolved_host: Optional[str] = None
        self._resolved_get_path: Optional[str] = None

        self.client = httpx.Client(
            headers={
                "Origin": "https://rumble.com",
                "Referer": "https://rumble.com/",
                # Use a browser-like UA; some shards behave differently with botty UAs
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
            },
            cookies=cookies,
            timeout=10.0,
            follow_redirects=True,
        )

    # ------------------------------------------------------------
    # SEND MESSAGE
    # ------------------------------------------------------------

    def send_message(self, channel_id: str, text: str) -> bool:
        host = self._resolved_host or self._preferred_host or "web7.rumble.com"
        url = f"https://{host}/chat/api/chat/{channel_id}/message"

        payload = {
            "data": {
                "request_id": uuid.uuid4().hex,
                "message": {"text": text},
                "rant": None,
                "channel_id": None,
            }
        }

        try:
            r = self.client.post(url, json=payload)

            if r.status_code != 200:
                # DO NOT print r.text (it may be huge/html/compressed)
                log.error(
                    f"Chat send failed [{r.status_code}] "
                    f"(host={host}, content-type={r.headers.get('content-type')})"
                )
                return False

            # If POST worked on this host, lock it in for subsequent calls
            self._resolved_host = host
            return True

        except Exception as e:
            log.error(f"Chat send exception (host={host}): {e}")
            return False

    # ------------------------------------------------------------
    # FETCH MESSAGES (POLL)
    # ------------------------------------------------------------

    def fetch_messages(
        self,
        channel_id: str,
        since_id: Optional[str] = None,
    ) -> List[dict]:
        """
        Poll chat messages.

        We auto-discover a working GET endpoint because:
        - /messages often returns a 404 HTML page on some shards/accounts
        - The correct endpoint varies by host/shard and sometimes by channel type
        """
        # First try with cached resolved endpoint (fast path)
        if self._resolved_host and self._resolved_get_path:
            msgs = self._try_fetch(
                host=self._resolved_host,
                path_tmpl=self._resolved_get_path,
                channel_id=channel_id,
                since_id=since_id,
            )
            if msgs is not None:
                return msgs

        # Otherwise discover (or re-discover)
        resolved = self._discover_poll_endpoint(channel_id=channel_id, since_id=since_id)
        if not resolved:
            return []

        host, path_tmpl = resolved
        msgs = self._try_fetch(host=host, path_tmpl=path_tmpl, channel_id=channel_id, since_id=since_id)
        return msgs or []

    # ------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------

    def _discover_poll_endpoint(self, channel_id: str, since_id: Optional[str]) -> Optional[Tuple[str, str]]:
        hosts = []
        if self._preferred_host:
            hosts.append(self._preferred_host)
        if self._resolved_host and self._resolved_host not in hosts:
            hosts.append(self._resolved_host)
        for h in self.HOSTS:
            if h not in hosts:
                hosts.append(h)

        # We only do a few lightweight probes each time; keep it bounded.
        for host in hosts:
            for path_tmpl in self.PATH_CANDIDATES:
                msgs = self._try_fetch(
                    host=host,
                    path_tmpl=path_tmpl,
                    channel_id=channel_id,
                    since_id=since_id,
                    probe=True,
                )
                if msgs is None:
                    continue

                # Success → cache and return
                self._resolved_host = host
                self._resolved_get_path = path_tmpl
                log.info(f"Resolved chat poll endpoint: https://{host}{path_tmpl.format(cid=channel_id)}")
                return host, path_tmpl

        log.error("Unable to resolve a working chat poll endpoint (all candidates failed)")
        return None

    def _try_fetch(
        self,
        host: str,
        path_tmpl: str,
        channel_id: str,
        since_id: Optional[str],
        probe: bool = False,
    ) -> Optional[List[dict]]:
        """
        Returns:
          - list[dict] if this endpoint works (even if empty)
          - None if endpoint clearly doesn't work (404/html/invalid)
        """
        # Most endpoints use ?after=... but some ignore it; harmless to send.
        params = {}
        if since_id:
            params["after"] = since_id

        url = f"https://{host}{path_tmpl.format(cid=channel_id)}"

        try:
            r = self.client.get(url, params=params)

            ct = (r.headers.get("content-type") or "").lower()

            # If it's HTML, it's almost certainly a routed 404/CF page.
            if "text/html" in ct:
                if not probe:
                    log.error(
                        f"Chat fetch failed [{r.status_code}] "
                        f"(host={host}, path={path_tmpl}, content-type={ct}, len={len(r.content)})"
                    )
                return None

            if r.status_code != 200:
                if not probe:
                    log.error(
                        f"Chat fetch failed [{r.status_code}] "
                        f"(host={host}, path={path_tmpl}, content-type={ct}, len={len(r.content)})"
                    )
                return None

            # Must be JSON to proceed
            try:
                payload = r.json()
            except Exception:
                if not probe:
                    log.error(
                        f"Chat fetch invalid JSON (host={host}, path={path_tmpl}, content-type={ct})"
                    )
                return None

            # Normalize possible shapes:
            # - {"data": [...]}
            # - {"data": {"messages": [...]}}
            # - {"messages": [...]}
            data = payload.get("data") if isinstance(payload, dict) else None

            msgs = None
            if isinstance(data, list):
                msgs = data
            elif isinstance(data, dict):
                if isinstance(data.get("messages"), list):
                    msgs = data["messages"]
                elif isinstance(data.get("data"), list):
                    msgs = data["data"]
            elif isinstance(payload, dict) and isinstance(payload.get("messages"), list):
                msgs = payload["messages"]

            if msgs is None:
                # This endpoint returned JSON but not messages; treat as non-working for polling.
                return None

            # Ensure list[dict]
            if not isinstance(msgs, list):
                return None

            out = [m for m in msgs if isinstance(m, dict)]
            return out

        except Exception as e:
            if not probe:
                log.error(f"Chat fetch exception (host={host}, path={path_tmpl}): {e}")
            return None
