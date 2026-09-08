"""Error alerts to the n8n "Engine Error Alerts" webhook.

Every unhandled exception in the FastAPI app is reported once, with the
request path and a short traceback, in the same shape the n8n engines use
(app / workflow / node / message / description / stack / url / mode). The
webhook URL is env-only. Reporting never raises: a broken alert channel must
not turn one failing request into two.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

APP_NAME = "startend-fastapi"
_STACK_LIMIT = 4000
# German first, plain, no stack trace for the visitor.
_ERROR_BODY = "Interner Fehler. Bitte versuchen Sie es in einer Minute erneut."


def alert_payload(
    *,
    workflow: str,
    node: str,
    message: str,
    description: str = "",
    stack: str = "",
    url: str = "",
) -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "workflow": workflow,
        "node": node,
        "message": message[:500],
        "description": description[:1000],
        "stack": stack[-_STACK_LIMIT:],
        "url": url,
        "mode": "production" if settings.session_https_only else "development",
    }


async def send_error_alert(
    *,
    workflow: str,
    node: str,
    message: str,
    description: str = "",
    stack: str = "",
    url: str = "",
) -> bool:
    """POST one alert. Returns True when the webhook accepted it, False when
    the webhook is unset, unreachable or rejects the payload — never raises."""
    webhook = settings.error_alert_webhook_url.strip()
    if not webhook:
        return False
    payload = alert_payload(
        workflow=workflow, node=node, message=message, description=description, stack=stack, url=url
    )
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(webhook, json=payload)
    except httpx.HTTPError as exc:
        logger.warning("error alert not delivered: %s", exc)
        return False
    if response.status_code >= 400:
        logger.warning("error alert rejected: %s %s", response.status_code, response.text[:200])
        return False
    return True


def install_error_alerts(app: FastAPI) -> None:
    """Report every unhandled exception, then answer 500 with a plain German
    line. HTTPException and validation errors keep FastAPI's own handlers."""

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> PlainTextResponse:
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        logger.exception("unhandled error on %s %s", request.method, request.url.path)
        await send_error_alert(
            workflow=request.url.path,
            node=f"{request.method} {request.url.path}",
            message=f"{type(exc).__name__}: {exc}",
            description=f"Unhandled exception while serving {request.method} {request.url.path}",
            stack=stack,
            url=str(request.url),
        )
        return PlainTextResponse(_ERROR_BODY, status_code=500)
