"""Stripe Checkout + webhook helpers for X Autopilot. Talks to Stripe over httpx."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

STRIPE_API = "https://api.stripe.com/v1"
PRODUCT_METADATA = "x-autopilot"


class StripeNotConfigured(RuntimeError):
    pass


class StripeError(RuntimeError):
    pass


class StripeSignatureError(ValueError):
    pass


def checkout_urls(base_url: str) -> tuple[str, str]:
    base = base_url.rstrip("/")
    success = f"{base}/x-autopilot/panel/login?session_id={{CHECKOUT_SESSION_ID}}"
    cancel = f"{base}/x-autopilot/"
    return success, cancel


def public_base_url(request_base: str, forwarded_proto: str | None, forwarded_host: str | None) -> str:
    if settings.public_base_url.strip():
        return settings.public_base_url.strip().rstrip("/")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto.split(',')[0].strip()}://{forwarded_host.split(',')[0].strip()}".rstrip("/")
    return request_base.rstrip("/")


async def stripe_request(method: str, path: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    if not settings.stripe_secret_key.strip():
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set")
    base = (settings.stripe_api_base or STRIPE_API).strip().rstrip("/")
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.request(
            method,
            f"{base}{path}",
            data=data,
            auth=(settings.stripe_secret_key, ""),
        )
    if response.status_code >= 400:
        logger.warning("Stripe %s %s failed: %s %s", method, path, response.status_code, response.text[:500])
        raise StripeError(f"Stripe API {response.status_code}")
    return response.json()


def _checkout_line_items() -> dict[str, str]:
    data: dict[str, str] = {"line_items[0][quantity]": "1"}
    price_id = settings.stripe_xautopilot_price_id.strip()
    if price_id:
        data["line_items[0][price]"] = price_id
        return data
    data["line_items[0][price_data][currency]"] = "chf"
    data["line_items[0][price_data][unit_amount]"] = str(int(settings.stripe_xautopilot_amount_cents))
    data["line_items[0][price_data][product_data][name]"] = "X Autopilot"
    if settings.stripe_xautopilot_mode == "subscription":
        data["line_items[0][price_data][recurring][interval]"] = "month"
    return data


async def create_checkout_session(base_url: str) -> dict[str, Any]:
    success_url, cancel_url = checkout_urls(base_url)
    mode = settings.stripe_xautopilot_mode.strip() or "payment"
    data = {
        "mode": mode,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": PRODUCT_METADATA,
        "metadata[product]": PRODUCT_METADATA,
        **_checkout_line_items(),
    }
    session = await stripe_request("POST", "/checkout/sessions", data)
    if not session.get("url"):
        raise StripeError("Checkout session missing url")
    return session


async def retrieve_checkout_session(session_id: str) -> dict[str, Any]:
    return await stripe_request("GET", f"/checkout/sessions/{session_id}")


async def refund_payment_intent(payment_intent_id: str) -> dict[str, Any]:
    return await stripe_request("POST", "/refunds", {"payment_intent": payment_intent_id})


def session_email(session: dict[str, Any]) -> str:
    details = session.get("customer_details") or {}
    email = (details.get("email") or session.get("customer_email") or "").strip().lower()
    return email


def session_is_paid(session: dict[str, Any]) -> bool:
    if session.get("payment_status") == "paid":
        return True
    return session.get("status") == "complete"


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
    signed = timestamp.encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise StripeSignatureError("signature mismatch")


def sign_webhook_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Test helper: build a Stripe-Signature header for `payload`."""
    ts = int(time.time() if timestamp is None else timestamp)
    signed = f"{ts}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"
