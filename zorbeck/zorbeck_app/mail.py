"""Outbound e-mail through the HQ Mail Lane n8n webhook (env-only URL)."""

from __future__ import annotations

import logging

import httpx

from zorbeck_app.config import settings

logger = logging.getLogger("zorbeck.mail")


class MailNotConfigured(RuntimeError):
    """HQ_MAIL_WEBHOOK_URL is not set."""


class MailError(RuntimeError):
    """The mail lane rejected the message or could not be reached."""


async def send_mail(subject: str, body: str, to: str) -> None:
    url = settings.hq_mail_webhook_url
    if not url:
        raise MailNotConfigured("HQ_MAIL_WEBHOOK_URL is not set")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json={"subject": subject, "body": body, "to": to})
    except httpx.HTTPError as exc:
        raise MailError(f"mail lane unreachable: {exc}") from exc
    if response.status_code >= 400:
        logger.warning("mail lane rejected message: %s %s", response.status_code, response.text[:300])
        raise MailError(f"mail lane responded {response.status_code}")
