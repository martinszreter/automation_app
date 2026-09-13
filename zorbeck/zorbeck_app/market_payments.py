"""Fixed-price promotion through Stripe Payment Links and signed fulfilment.

Return-page URLs never grant benefits. Only a matching, paid Stripe event may
activate an order, and refund/dispute events revoke its promotion.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from zorbeck_app.accounts import account_page, checked
from zorbeck_app.config import settings
from zorbeck_app.market_security import read_input, require_user, user_for
from zorbeck_app.market_store import database, enqueue_lead, rate_limit
from zorbeck_app.stripe_api import StripeSignatureError, verify_stripe_signature

router = APIRouter()
PROMOTION_CENTS = 4900
PROMOTION_DAYS = 30


def configured(kind="promotion"):
    link = settings.smoke_link if kind == "smoke" else settings.promotion_link
    identifier = settings.smoke_link_id if kind == "smoke" else settings.promotion_link_id
    url = urlsplit(link)
    return bool(settings.marketplace_webhook_secret and identifier.startswith("plink_") and
                url.scheme == "https" and url.netloc == "buy.stripe.com" and not url.query and not url.fragment)


@router.get("/promote/{listing_id}")
async def promotion_page(request: Request, listing_id: str):
    user = user_for(request)
    if not user:
        return RedirectResponse("/login", 303)
    with database() as conn:
        row = conn.execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
        active = conn.execute("SELECT MAX(promotion_until) FROM orders WHERE listing_id=? AND status='paid'",
                              (listing_id,)).fetchone()[0]
    if not row:
        raise HTTPException(404, "This property is not in your account.")
    return account_page(request, "market-promote.html", listing=dict(row), property=json.loads(row["data_json"]),
                        promotion_active=bool(active and active>time.time()), payments_ready=configured())


@router.post("/api/payments/start")
async def start_payment(request: Request):
    user = require_user(request)
    data = await read_input(request)
    rate_limit("checkout:"+user["id"], 10, 3600)
    kind = data.get("kind", "promotion")
    if kind not in {"promotion", "smoke"} or (kind == "smoke" and user["role"] != "admin"):
        raise HTTPException(403, "This purchase is unavailable.")
    if not checked(data.get("terms")):
        raise HTTPException(400, "Please accept the promotion terms before continuing.")
    if not configured(kind):
        raise HTTPException(503, "Checkout is temporarily unavailable. Your property remains saved.")
    listing_id = str(data.get("listing_id") or "") if kind == "promotion" else None
    now = int(time.time())
    with database(write=True) as conn:
        if kind == "promotion":
            row = conn.execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
            if not row:
                raise HTTPException(404, "This property is not in your account.")
            if row["status"] != "published" or row["updated_at"] <= now-90*86400:
                raise HTTPException(409, "Your property must be reviewed and published before you can feature it.")
            active = conn.execute("SELECT id FROM orders WHERE listing_id=? AND status='paid' AND promotion_until>?",
                                  (listing_id, now)).fetchone()
            if active:
                raise HTTPException(409, "Your property is already featured. You can renew after it ends.")
            if not checked(data.get("availability_confirmed")):
                raise HTTPException(400, "Please confirm that your property is still available and its details are current.")
            conn.execute("UPDATE listings SET updated_at=? WHERE id=?", (now, listing_id))
        # Reuse an outstanding order so a double click cannot create two entitlements.
        order = conn.execute("SELECT id FROM orders WHERE user_id=? AND kind=? AND listing_id IS ? AND status='pending' "
                             "ORDER BY created_at DESC LIMIT 1", (user["id"], kind, listing_id)).fetchone()
        order_id = order["id"] if order else secrets.token_hex(24)
        link_id = settings.smoke_link_id if kind == "smoke" else settings.promotion_link_id
        if not order:
            conn.execute("INSERT INTO orders(id,user_id,listing_id,kind,amount_cents,payment_link_id,created_at) VALUES (?,?,?,?,?,?,?)",
                         (order_id, user["id"], listing_id, kind, 100 if kind == "smoke" else PROMOTION_CENTS, link_id, now))
    link = settings.smoke_link if kind == "smoke" else settings.promotion_link
    # Opaque reference only; email and private listing content never enter a URL.
    return {"ok": True, "checkout_url": link+"?"+urlencode({"client_reference_id": order_id})}


@router.get("/payments/return")
async def payment_return(request: Request):
    if not user_for(request):
        return account_page(request, "market-payment.html", session_id="", signed_in=False)
    identifier = request.query_params.get("session_id", "")
    if not re.fullmatch(r"cs_(?:test_|live_)?[A-Za-z0-9_]{8,200}", identifier):
        identifier = ""
    return account_page(request, "market-payment.html", session_id=identifier, signed_in=True)


@router.get("/api/payments/status")
async def payment_status(request: Request):
    user = require_user(request)
    session_id = request.query_params.get("session_id", "")[:250]
    with database() as conn:
        row = conn.execute("SELECT status,kind,listing_id,promotion_until FROM orders WHERE session_id=? AND user_id=?",
                           (session_id, user["id"])).fetchone()
    return JSONResponse({"status": row["status"] if row else "pending", "order": dict(row) if row else None},
                        headers={"Cache-Control": "no-store"})


def process_event(event: dict):
    event_id, event_type = event.get("id"), event.get("type")
    obj = (event.get("data") or {}).get("object") if isinstance(event.get("data"), dict) else None
    if not isinstance(event_id, str) or not event_id.startswith("evt_") or not isinstance(obj, dict):
        raise HTTPException(400, "Invalid event.")
    expected_live = not settings.stub
    if event.get("livemode") is not expected_live:
        return {"received": True, "ignored": "mode"}
    now = int(time.time())
    with database(write=True) as conn:
        if conn.execute("SELECT 1 FROM payment_events WHERE id=?", (event_id,)).fetchone():
            return {"received": True, "duplicate": True}
        conn.execute("INSERT INTO payment_events VALUES (?,?,?)", (event_id, str(event_type), now))
        if event_type in {"charge.refunded", "charge.dispute.created"}:
            intent = obj.get("payment_intent")
            if isinstance(intent, str) and intent.startswith("pi_"):
                reason = "refunded" if event_type == "charge.refunded" else "disputed"
                conn.execute("INSERT OR REPLACE INTO payment_blocks VALUES (?,?,?)", (intent, reason, now))
                conn.execute("UPDATE orders SET status=?,promotion_until=NULL WHERE payment_intent=?", (reason, intent))
            return {"received": True}
        if event_type not in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
            return {"received": True, "ignored": "event"}
        if obj.get("payment_status") != "paid":
            return {"received": True, "ignored": "unpaid"}
        metadata = obj.get("metadata") or {}
        order_id, session_id, intent = obj.get("client_reference_id"), obj.get("id"), obj.get("payment_intent")
        if not isinstance(order_id, str) or not isinstance(session_id, str) or not isinstance(intent, str):
            return {"received": True, "ignored": "reference"}
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            return {"received": True, "ignored": "unknown_order"}
        correct = (
            isinstance(metadata, dict) and metadata.get("venture") == "zorbeck"
            and metadata.get("offering") == row["kind"] and obj.get("mode") == "payment"
            and obj.get("currency") == "chf" and obj.get("amount_total") == row["amount_cents"]
            and obj.get("payment_link") == row["payment_link_id"] and obj.get("livemode") is expected_live
            and session_id.startswith("cs_") and intent.startswith("pi_")
        )
        if not correct:
            conn.execute("INSERT OR IGNORE INTO payment_exceptions VALUES (?,?,?,?)", (session_id, order_id, "payment_mismatch", now))
            return {"received": True, "ignored": "payment_mismatch"}
        if row["session_id"]:
            if row["session_id"] != session_id:
                conn.execute("INSERT OR IGNORE INTO payment_exceptions VALUES (?,?,?,?)", (session_id, order_id, "duplicate_purchase_review_refund", now))
            return {"received": True, "duplicate": True}
        if conn.execute("SELECT 1 FROM orders WHERE session_id=?", (session_id,)).fetchone():
            return {"received": True, "ignored": "session_already_assigned"}
        block = conn.execute("SELECT reason FROM payment_blocks WHERE payment_intent=?", (intent,)).fetchone()
        status = block["reason"] if block else "paid"
        until = now + PROMOTION_DAYS*86400 if status == "paid" and row["kind"] == "promotion" else None
        if until:
            listing = conn.execute("SELECT status,updated_at FROM listings WHERE id=?", (row["listing_id"],)).fetchone()
            if not listing or listing["status"] != "published" or listing["updated_at"] <= now-90*86400:
                status, until = "review_required", None
                conn.execute("INSERT OR IGNORE INTO payment_exceptions VALUES (?,?,?,?)", (session_id, order_id, "listing_unavailable_review_refund", now))
        conn.execute("UPDATE orders SET status=?,session_id=?,payment_intent=?,paid_at=?,promotion_until=? WHERE id=?",
                     (status, session_id, intent, now, until, order_id))
        email = conn.execute("SELECT email,marketing FROM users WHERE id=?", (row["user_id"],)).fetchone()
        enqueue_lead(conn, "payment:"+session_id, email["email"], "paid", order_id=order_id,
                     amount_cents=row["amount_cents"], currency="CHF", product=row["kind"], marketing_consent=bool(email["marketing"]))
    return {"received": True}


@router.post("/api/marketplace/stripe")
async def payment_webhook(request: Request):
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > 262144:
            raise HTTPException(413, "Event too large.")
    try:
        verify_stripe_signature(bytes(payload), request.headers.get("stripe-signature", ""), settings.marketplace_webhook_secret)
    except StripeSignatureError:
        return JSONResponse({"error": "invalid signature"}, status_code=400)
    try:
        event = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid event.") from None
    if not isinstance(event, dict):
        raise HTTPException(400, "Invalid event.")
    return process_event(event)
