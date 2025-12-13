import re
from typing import Dict, Optional

from services.rumble.browser.browser_client import RumbleBrowserClient
from shared.logging.logger import get_logger

log = get_logger("rumble.api.watch_page")

ROOM_RE = re.compile(r"(?:roomId|chatRoomId)=([^&]+)")
POST_RE = re.compile(r"(?:postPath|chatPostPath)=([^&]+)")


async def fetch_watch_page_chat_state(watch_url: str) -> Dict[str, Optional[str]]:
    """
    Extract Rumble livestream chat metadata by recursively traversing
    DOM + shadow DOM and locating the embedded chat iframe.

    This handles rumble-player → rumble-live-chat → iframe.
    """
    browser = RumbleBrowserClient.instance()
    page = await browser.get_page(watch_url)

    try:
        # Allow player + chat boot
        await page.wait_for_timeout(5000)

        iframe_src = await page.evaluate(
            """
            () => {
              const seen = new Set();

              function walk(node) {
                if (!node || seen.has(node)) return null;
                seen.add(node);

                // iframe check
                if (node.tagName === 'IFRAME' && node.src && node.src.includes('/chat')) {
                  return node.src;
                }

                // shadow root
                if (node.shadowRoot) {
                  const found = walk(node.shadowRoot);
                  if (found) return found;
                }

                // children
                if (node.children) {
                  for (const child of node.children) {
                    const found = walk(child);
                    if (found) return found;
                  }
                }

                return null;
              }

              return walk(document.body);
            }
            """
        )

        if not iframe_src:
            raise RuntimeError("Chat iframe not found in DOM or shadow DOM")

        room_match = ROOM_RE.search(iframe_src)
        post_match = POST_RE.search(iframe_src)

        if not room_match or not post_match:
            raise RuntimeError(f"Chat iframe src missing metadata: {iframe_src}")

        room_id = room_match.group(1)
        post_path = post_match.group(1)

        log.info(f"Extracted chat metadata via deep shadow scan: room={room_id}")

        return {
            "is_live": True,
            "chat_room_id": room_id,
            "chat_post_path": post_path,
        }

    except Exception as e:
        log.error(f"No livestream chat session detected: {e}")

        return {
            "is_live": False,
            "chat_room_id": None,
            "chat_post_path": None,
        }
