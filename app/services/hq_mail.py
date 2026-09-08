"""Outbound email via the HQ Mail Lane n8n webhook.

The webhook URL is env-only: it is a write endpoint, so it never enters the
repo. Recipient defaults to whatever the n8n workflow is configured to send
to; pass ``to`` only when a message needs a different destination.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class HQMailNotConfigured(RuntimeError):
    """HQ_MAIL_WEBHOOK_URL is not set."""


class HQMailError(RuntimeError):
    """HQ Mail rejected the message or could not be reached."""


async def send_hq_mail(subject: str, body: str, *, to: str | None = None) -> None:
    url = settings.hq_mail_webhook_url.strip()
    if not url:
        raise HQMailNotConfigured("HQ_MAIL_WEBHOOK_URL is not set")
    payload: dict[str, Any] = {"subject": subject, "body": body}
    if to:
        payload["to"] = to
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise HQMailError(f"HQ Mail request failed: {exc}") from exc
    if response.status_code >= 400:
        logger.warning("HQ Mail rejected message: %s %s", response.status_code, response.text[:300])
        raise HQMailError(f"HQ Mail responded {response.status_code}")
