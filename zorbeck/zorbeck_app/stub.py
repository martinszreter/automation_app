"""CI stand-in for Stripe, the mail lane, the alert handler and the lead sink.

Mounted under ``/_stub`` only when ``ZORBECK_STUB=1``. The app itself does not
know it is talking to the stub: ``STRIPE_API_BASE``, ``HQ_MAIL_WEBHOOK_URL``,
``ALERT_WEBHOOK_URL`` and ``SIGNUP_WEBHOOK_URL`` simply point here, and the
webhook the stub sends back is signed with ``STRIPE_WEBHOOK_SECRET`` exactly
like Stripe would. Everything lives in memory and is wiped on restart.

Never set ``ZORBECK_STUB`` on the Railway service: the stub "pays" anything.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any
from urllib.parse import parse_qsl

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from zorbeck_app.config import settings
from zorbeck_app.money import chf
from zorbeck_app.stripe_api import sign_webhook_payload

router = APIRouter(prefix="/_stub", include_in_schema=False)

sessions: dict[str, dict[str, Any]] = {}
outbox: list[dict[str, Any]] = []
alerts: list[dict[str, Any]] = []
leads: list[dict[str, Any]] = []
webhook_deliveries: list[dict[str, Any]] = []


def reset() -> None:
    sessions.clear()
    outbox.clear()
    alerts.clear()
    leads.clear()
    webhook_deliveries.clear()


def _nested(flat: dict[str, str]) -> dict[str, Any]:
    """Unflatten Stripe's form encoding: a[b][c]=v -> {a: {b: {c: v}}}."""
    result: dict[str, Any] = {}
    for key, value in flat.items():
        parts = [p for p in key.replace("]", "").split("[") if p != ""]
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return result


def _line_amount(payload: dict[str, Any]) -> int:
    items = payload.get("line_items") or {}
    first = items.get("0") if isinstance(items, dict) else None
    if not isinstance(first, dict):
        return 0
    price_data = first.get("price_data") or {}
    if isinstance(price_data, dict) and price_data.get("unit_amount"):
        return int(price_data["unit_amount"])
    # A Price id has no amount in the request; the stub charges the configured price.
    return int(settings.price_cents)


# --- Stripe: /v1 ------------------------------------------------------------


@router.post("/v1/checkout/sessions")
async def create_session(request: Request) -> JSONResponse:
    body = await request.body()
    payload = _nested(dict(parse_qsl(body.decode("utf-8"))))
    session_id = "cs_test_stub_" + secrets.token_hex(6)
    base = str(request.base_url).rstrip("/")
    session = {
        "id": session_id,
        "object": "checkout.session",
        "mode": payload.get("mode", "payment"),
        "status": "open",
        "payment_status": "unpaid",
        "currency": "chf",
        "amount_total": _line_amount(payload),
        "customer_email": payload.get("customer_email"),
        "customer_details": None,
        "metadata": payload.get("metadata") or {},
        "client_reference_id": payload.get("client_reference_id"),
        "success_url": payload.get("success_url", ""),
        "cancel_url": payload.get("cancel_url", ""),
        "payment_intent": None,
        "url": f"{base}/_stub/checkout/{session_id}",
        "created": int(time.time()),
    }
    sessions[session_id] = session
    return JSONResponse(session)


@router.get("/v1/checkout/sessions/{session_id}")
async def get_session(session_id: str) -> JSONResponse:
    session = sessions.get(session_id)
    if session is None:
        return JSONResponse({"error": {"message": "No such checkout.session"}}, status_code=404)
    return JSONResponse(session)


# --- Stripe: hosted checkout page ---------------------------------------------


@router.get("/checkout/{session_id}", response_class=HTMLResponse)
async def checkout_page(session_id: str) -> HTMLResponse:
    session = sessions.get(session_id)
    if session is None:
        return HTMLResponse("<h1>Unbekannte Session</h1>", status_code=404)
    amount = chf(int(session["amount_total"]))
    return HTMLResponse(
        "<!doctype html><html lang='de'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Stub Checkout</title></head><body>"
        "<h1>Stripe Checkout (Stub)</h1>"
        f"<p data-testid='stub-amount'>Zu zahlen: <strong>{amount}</strong></p>"
        f"<p data-testid='stub-email'>{session.get('customer_email') or ''}</p>"
        f"<form method='post' action='/_stub/checkout/{session_id}/pay'>"
        "<button type='submit' data-testid='stub-pay'>Bezahlen</button></form>"
        "</body></html>"
    )


@router.post("/checkout/{session_id}/pay")
async def pay(session_id: str, request: Request) -> RedirectResponse:
    session = sessions.get(session_id)
    if session is None:
        return RedirectResponse("/", status_code=303)
    session["payment_status"] = "paid"
    session["status"] = "complete"
    session["payment_intent"] = "pi_test_stub_" + secrets.token_hex(6)
    session["customer_details"] = {"email": session.get("customer_email"), "name": None}

    event = {
        "id": "evt_test_stub_" + secrets.token_hex(6),
        "object": "event",
        "type": "checkout.session.completed",
        "created": int(time.time()),
        "data": {"object": session},
    }
    payload = json.dumps(event).encode("utf-8")
    base = str(request.base_url).rstrip("/")
    delivery: dict[str, Any] = {"session_id": session_id, "status": None, "error": None}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base}/stripe/webhook",
                content=payload,
                headers={
                    "content-type": "application/json",
                    "stripe-signature": sign_webhook_payload(payload, settings.stripe_webhook_secret),
                },
            )
        delivery["status"] = response.status_code
    except httpx.HTTPError as exc:  # pragma: no cover - network failure inside CI
        delivery["error"] = str(exc)
    webhook_deliveries.append(delivery)

    success = str(session["success_url"]).replace("{CHECKOUT_SESSION_ID}", session_id)
    return RedirectResponse(success, status_code=303)


# --- mail lane, alert handler, lead sink --------------------------------------


@router.post("/mail")
async def mail_sink(request: Request) -> JSONResponse:
    outbox.append(await request.json())
    return JSONResponse({"ok": True})


@router.get("/mail/outbox")
async def mail_outbox() -> JSONResponse:
    return JSONResponse(outbox)


@router.post("/alerts")
async def alert_sink(request: Request) -> JSONResponse:
    alerts.append(await request.json())
    return JSONResponse({"message": "Workflow got started."})


@router.get("/alerts")
async def alert_list() -> JSONResponse:
    return JSONResponse(alerts)


@router.post("/leads")
async def lead_sink(request: Request) -> JSONResponse:
    leads.append(await request.json())
    return JSONResponse({"ok": True})


@router.get("/leads")
async def lead_list() -> JSONResponse:
    return JSONResponse(leads)


@router.get("/webhooks")
async def webhook_list() -> JSONResponse:
    return JSONResponse(webhook_deliveries)


@router.post("/reset")
async def reset_all() -> JSONResponse:
    reset()
    return JSONResponse({"ok": True})


@router.get("/boom")
async def boom() -> None:
    """Deliberate 500 so CI can prove the error alert reaches the handler."""
    raise RuntimeError("stub: deliberate failure for the alert test")
