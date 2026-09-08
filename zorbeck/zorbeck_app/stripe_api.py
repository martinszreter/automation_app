"""Stripe Checkout over the REST API (httpx), plus webhook signature checks.

The API base is configurable only so the CI stub (``zorbeck_app.stub``) can
answer in place of api.stripe.com; the code path is otherwise identical.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from zorbeck_app.config import settings

logger = logging.getLogger("zorbeck.stripe")

VENTURE = "zorbeck"


class StripeNotConfigured(RuntimeError):
    pass


class StripeError(RuntimeError):
    pass


class StripeSignatureError(ValueError):
    pass


def checkout_urls(base_url: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    return f"{base}/danke?session_id={{CHECKOUT_SESSION_ID}}", f"{base}/?abgebrochen=1"


async def stripe_request(method: str, path: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    if not settings.stripe_secret_key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set")
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.request(
                method,
                f"{settings.stripe_api_base}{path}",
                data=data,
                auth=(settings.stripe_secret_key, ""),
            )
        except httpx.HTTPError as exc:
            raise StripeError(f"Stripe unreachable: {exc}") from exc
    if response.status_code >= 400:
        logger.warning("Stripe %s %s failed: %s %s", method, path, response.status_code, response.text[:300])
        raise StripeError(f"Stripe API {response.status_code}")
    return response.json()


def build_checkout_payload(base_url: str, email: str, metadata: dict[str, str]) -> dict[str, str]:
    success_url, cancel_url = checkout_urls(base_url)
    data: dict[str, str] = {
        "mode": "payment",
        "locale": "de",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "customer_email": email,
        "client_reference_id": VENTURE,
        "metadata[venture]": VENTURE,
        "line_items[0][quantity]": "1",
    }
    for key, value in metadata.items():
        data[f"metadata[{key}]"] = value
    if settings.stripe_price_id:
        data["line_items[0][price]"] = settings.stripe_price_id
    else:
        data["line_items[0][price_data][currency]"] = "chf"
        data["line_items[0][price_data][unit_amount]"] = str(int(settings.price_cents))
        data["line_items[0][price_data][product_data][name]"] = "Zorbeck Deal-Alarm"
    return data


async def create_checkout_session(base_url: str, email: str, metadata: dict[str, str]) -> dict[str, Any]:
    session = await stripe_request("POST", "/checkout/sessions", build_checkout_payload(base_url, email, metadata))
    if not session.get("url"):
        raise StripeError("Checkout session missing url")
    return session


async def retrieve_checkout_session(session_id: str) -> dict[str, Any]:
    return await stripe_request("GET", f"/checkout/sessions/{session_id}")


def session_email(session: dict[str, Any]) -> str:
    details = session.get("customer_details") or {}
    return str(details.get("email") or session.get("customer_email") or "").strip().lower()


def session_is_paid(session: dict[str, Any]) -> bool:
    return session.get("payment_status") == "paid" or session.get("status") == "complete"


def verify_stripe_signature(payload: bytes, header: str, secret: str, tolerance_seconds: int = 300) -> None:
    if not secret.strip():
        raise StripeSignatureError("webhook secret is not set")
    parsed: dict[str, list[str]] = {}
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key:
            parsed.setdefault(key, []).append(value)
    timestamp = (parsed.get("t") or [""])[0]
    signatures = parsed.get("v1") or []
    if not timestamp or not signatures:
        raise StripeSignatureError("malformed Stripe-Signature header")
    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise StripeSignatureError("invalid timestamp") from exc
    if abs(time.time() - ts) > tolerance_seconds:
        raise StripeSignatureError("timestamp outside tolerance")
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise StripeSignatureError("signature mismatch")


def sign_webhook_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-Signature header for ``payload`` (tests and the stub)."""
    ts = int(time.time() if timestamp is None else timestamp)
    digest = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"
