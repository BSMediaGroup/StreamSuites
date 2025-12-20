from copy import deepcopy
from typing import Dict, Any


def merge_ratelimits(
    *,
    schema: Dict[str, Any],
    creator_id: str,
    platform: str | None,
    creator_limits: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """
    Merge rate limits in the following order:
    schema.global
    -> schema.platforms[platform]
    -> schema.creators[creator_id].overrides
    -> creator_limits (dashboard export)

    Returns a fully-resolved limits dict.
    """

    resolved: Dict[str, Any] = {}

    # 1. Global defaults
    resolved.update(schema.get("global", {}))

    # 2. Platform defaults
    if platform:
        resolved.update(schema.get("platforms", {}).get(platform, {}))

    # 3. Creator overrides (schema-defined)
    resolved.update(
        schema.get("creators", {})
        .get(creator_id, {})
        .get("overrides", {})
    )

    # 4. Dashboard-authored creator limits
    if creator_limits:
        resolved.update(creator_limits)

    return resolved
