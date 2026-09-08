"""Error alerts: one JSON message per unhandled 5xx to the n8n workflow
"Engine Error Alerts" (N6gYXlzZUn6OXOs4), which classifies the failure and
emails the diagnosis.

The webhook URL is env-only (``ERROR_ALERT_WEBHOOK_URL``): it is a write key.
Reporting never raises — an alert that fails must not turn one error into two
— and never blocks the response for more than a few seconds. The payload
carries no request body, no headers and no cookies: path, method, exception
type, message and a timestamp are enough for the diagnosis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5.0
_MESSAGE_MAX = 600


def build_alert(
    *,
    path: str,
    method: str,
    error: BaseException,
    service: str | None = None,
    status: int = 500,
) -> dict[str, Any]:
    """The message shape the workflow receives. Pure — unit-tested."""
    return {
        "service": service or settings.service_name,
        "path": path,
        "method": method.upper(),
        "status": status,
        "error": f"{type(error).__name__}: {str(error)[:_MESSAGE_MAX]}",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def report_error(path: str, method: str, error: BaseException, *, status: int = 500) -> bool:
    """Post the alert. Returns True when the webhook accepted it, False when
    it is not configured or could not be reached — never raises."""
    url = settings.error_alert_webhook_url.strip()
    if not url:
        logger.error("unhandled %s %s: %r (ERROR_ALERT_WEBHOOK_URL not set)", method, path, error)
        return False
    payload = build_alert(path=path, method=method, error=error, status=status)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.error("error alert not delivered for %s %s: %s", method, path, exc)
        return False
    if response.status_code >= 400:
        logger.error("error alert rejected (%s) for %s %s", response.status_code, method, path)
        return False
    return True
