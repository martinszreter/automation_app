"""Transport for the n8n data table webhooks.

Both ventures store their order rows by POSTing one JSON row to an n8n
webhook whose URL is env-only (an n8n webhook is a write key, so it never
enters the repo). The URL lookup and the venture-specific exceptions stay with
each venture; the HTTP call and its error mapping live here once.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20.0


async def post_row(url: str, row: dict[str, Any], *, error: type[Exception]) -> None:
    """POST ``row`` to ``url``; raise ``error`` if n8n cannot be reached or rejects it."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=row)
    except httpx.HTTPError as exc:
        raise error(f"n8n request failed: {exc}") from exc
    if response.status_code >= 400:
        logger.warning(
            "n8n %s/%s row rejected: %s %s",
            row.get("table"),
            row.get("kind"),
            response.status_code,
            response.text[:300],
        )
        raise error(f"n8n responded {response.status_code}")
