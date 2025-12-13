import asyncio
import json
import re
from typing import Dict, Optional, Tuple

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")

ROOM_RE = re.compile(r'(?:roomId|chatRoomId)\s*["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)
POST_RE = re.compile(r'(?:postPath|chatPostPath)\s*["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.IGNORECASE)


def _find_in_text(s: str) -> Tuple[Optional[str], Optional[str]]:
    if not s:
        return None, None
    m1 = ROOM_RE.search(s)
    m2 = POST_RE.search(s)
    room = m1.group(1) if m1 else None
    post = m2.group(1) if m2 else None
    return room, post


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Load a Rumble livestream watch page and extract chat metadata.

    Strategy (in order):
      1) BrowserClient session discovery (responses/ws/dom) with a poll window
      2) Frame/iframe URL + frame HTML scan
      3) Full page HTML scan
      4) Last-resort JS deep scan of window/global objects
    """
    browser = RumbleBrowserClient.instance()
    browser.clear_sessions()

    page = await browser.get_page(watch_url)

    # 1) Poll for any discovered session for up to ~20s
    deadline = asyncio.get_event_loop().time() + 20.0
    while asyncio.get_event_loop().time() < deadline:
        sess = browser.get_latest_session()
        if sess and sess.get("room_id") and sess.get("post_path"):
            return {
                "is_live": True,
                "chat_room_id": sess["room_id"],
                "chat_post_path": sess["post_path"],
            }
        await asyncio.sleep(0.5)

    # 2) Scan frames/iframes (URL + HTML)
    try:
        for frame in page.frames:
            try:
                # Frame URL scan
                fr_url = frame.url or ""
                r, p = _find_in_text(fr_url)
                if r and p:
                    log.info(f"Extracted chat metadata from frame URL: room={r}")
                    return {"is_live": True, "chat_room_id": r, "chat_post_path": p}

                # Frame HTML scan (can be heavy; keep it guarded)
                html = await frame.content()
                r2, p2 = _find_in_text(html)
                if r2 and p2:
                    log.info(f"Extracted chat metadata from frame HTML: room={r2}")
                    return {"is_live": True, "chat_room_id": r2, "chat_post_path": p2}
            except Exception:
                continue
    except Exception:
        pass

    # 3) Full page HTML scan
    try:
        html = await page.content()
        r, p = _find_in_text(html)
        if r and p:
            log.info(f"Extracted chat metadata from page HTML: room={r}")
            return {"is_live": True, "chat_room_id": r, "chat_post_path": p}
    except Exception:
        pass

    # 4) Last-resort JS deep scan
    try:
        result = await page.evaluate(
            """
            () => {
              const seen = new Set();
              const maxNodes = 20000;

              function walk(obj) {
                if (!obj || typeof obj !== 'object') return null;
                if (seen.has(obj)) return null;
                seen.add(obj);
                if (seen.size > maxNodes) return null;

                // Direct key checks
                const room = obj.roomId || obj.chatRoomId;
                const post = obj.postPath || obj.chatPostPath;
                if (typeof room === 'string' && room && typeof post === 'string' && post) {
                  return { room, post };
                }

                if (Array.isArray(obj)) {
                  for (const item of obj) {
                    const found = walk(item);
                    if (found) return found;
                  }
                  return null;
                }

                // walk object properties
                for (const k of Object.keys(obj)) {
                  try {
                    const found = walk(obj[k]);
                    if (found) return found;
                  } catch (e) {}
                }
                return null;
              }

              // Candidates
              const candidates = [
                window.__NUXT__,
                window.$nuxt,
                window.__INITIAL_STATE__,
                window.__NEXT_DATA__,
                window,
              ];

              for (const c of candidates) {
                try {
                  const found = walk(c);
                  if (found) return found;
                } catch (e) {}
              }

              return null;
            }
            """
        )

        if result and result.get("room") and result.get("post"):
            log.info(f"Extracted chat metadata from JS deep scan: room={result['room']}")
            return {
                "is_live": True,
                "chat_room_id": result["room"],
                "chat_post_path": result["post"],
            }
    except Exception as e:
        log.debug(f"JS deep scan failed: {e}")

    log.error("No livestream chat session detected after navigation")

    return {
        "is_live": False,
        "chat_room_id": None,
        "chat_post_path": None,
    }
