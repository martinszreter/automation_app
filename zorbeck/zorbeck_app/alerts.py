"""Error alerts to the shared n8n handler "Engine Error Alerts" (N6gYXlzZUn6OXOs4).

The handler's external entry takes ``{app, workflow, node, message,
description, stack, url, mode}``, classifies the failure and e-mails the
diagnosis; repeats of one fault are suppressed there for 24 h. The webhook URL
is env-only (``ALERT_WEBHOOK_URL``). Alerting never raises: a failing alert
must not turn a handled error into a second one.
"""

from __future__ import annotations

import logging
import traceback

import httpx

from zorbeck_app.config import settings

logger = logging.getLogger("zorbeck.alerts")

APP_NAME = "zorbeck"


def alert_payload(node: str, message: str, *, description: str = "", stack: str = "", url: str = "") -> dict[str, str]:
    return {
        "app": APP_NAME,
        "workflow": APP_NAME,
        "node": node,
        "message": message[:500],
        "description": description[:1000],
        "stack": stack[:2000],
        "url": url,
        "mode": "production",
    }


async def send_alert(node: str, message: str, *, description: str = "", exc: BaseException | None = None, url: str = "") -> bool:
    """Post one alert. Returns True when the handler accepted it."""
    stack = "".join(traceback.format_exception(exc)) if exc is not None else ""
    payload = alert_payload(node, message, description=description, stack=stack, url=url)
    if not settings.alert_webhook_url:
        logger.error("alert (ALERT_WEBHOOK_URL unset): %s %s", node, message)
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.alert_webhook_url, json=payload)
    except httpx.HTTPError as exc_:
        logger.error("alert delivery failed: %s (%s %s)", exc_, node, message)
        return False
    if response.status_code >= 400:
        logger.error("alert rejected: %s (%s %s)", response.status_code, node, message)
        return False
    return True
