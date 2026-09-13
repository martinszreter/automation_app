"""Customer accounts; no external auth service or email-delivery dependency."""
from __future__ import annotations

import asyncio
import hmac
import json
import secrets
import sqlite3
import time

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from zorbeck_app.config import settings
from zorbeck_app.market_security import (
    DUMMY_HASH, auth_limit, csrf_cookie, csrf_for, digest, email_address,
    password_hash, password_matches, read_input, require_user, safe_next,
    session_cookie, set_csrf, start_session, user_for, validate_password,
)
from zorbeck_app.market_store import database, enqueue_lead, rate_limit

router = APIRouter()
hash_slots = asyncio.Semaphore(4)
outbox_lock = asyncio.Lock()


def checked(value):
    return value is True or value in ("on", "true", "1")


def account_page(request, template, **context):
    from zorbeck_app.main import render
    token = csrf_for(request)
    response = render(request, template, user=user_for(request), csrf=token, **context)
    set_csrf(response, token)
    response.headers["Cache-Control"] = "no-store"
    if request.url.path not in {"/sell", "/terms/marketplace"}:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


async def flush_leads():
    """Retry only the existing lead sink. No passwords, recovery keys or photos."""
    if not settings.signup_webhook_url or not settings.marketplace_db_path or outbox_lock.locked():
        return
    async with outbox_lock:
        with database() as conn:
            rows = conn.execute("SELECT * FROM lead_outbox WHERE delivered_at IS NULL AND next_attempt<=? LIMIT 10",
                                (int(time.time()),)).fetchall()
        async with httpx.AsyncClient(timeout=8) as client:
            for row in rows:
                delivered = None
                try:
                    response = await client.post(settings.signup_webhook_url, json=json.loads(row["payload"]))
                    response.raise_for_status()
                    try:
                        receipt = response.json()
                    except ValueError:
                        receipt = None
                    if isinstance(receipt, dict) and receipt.get("ok") is False:
                        raise ValueError("Lead sink declined")
                    delivered = int(time.time())
                except (httpx.HTTPError, ValueError):
                    pass  # Persist the retry without logging a secret URL or customer data.
                with database(write=True) as conn:
                    delay = min(86400, 60 * 2 ** min(row["attempts"], 10))
                    conn.execute("UPDATE lead_outbox SET attempts=attempts+1,next_attempt=?,delivered_at=? WHERE id=?",
                                 (int(time.time())+delay, delivered, row["id"]))


@router.get("/login")
@router.get("/register")
@router.get("/recover")
async def login_page(request: Request):
    mode = request.url.path[1:]
    if user_for(request) and mode != "recover":
        return RedirectResponse(safe_next(request.query_params.get("next")), 303)
    return account_page(request, "market-auth.html", mode=mode, next_path=safe_next(request.query_params.get("next")))


@router.get("/api/me")
async def me(request: Request):
    token = csrf_for(request)
    response = JSONResponse({"user": user_for(request), "csrf": token}, headers={"Cache-Control": "no-store"})
    set_csrf(response, token)
    return response


@router.post("/api/account/register")
async def register(request: Request, background: BackgroundTasks):
    data = await read_input(request)
    email = email_address(data.get("email"))
    auth_limit(request, email)
    password = validate_password(data.get("password"))
    if not checked(data.get("terms")):
        raise HTTPException(400, "Please accept the account terms and privacy notice.")
    user_id, recovery = secrets.token_hex(16), secrets.token_urlsafe(32)
    async with hash_slots:
        hashed = await run_in_threadpool(password_hash, password)
    try:
        with database(write=True) as conn:
            conn.execute("INSERT INTO users(id,email,password_hash,recovery_hash,marketing,created_at) VALUES (?,?,?,?,?,?)",
                         (user_id, email, hashed, digest(recovery), int(checked(data.get("marketing"))), int(time.time())))
            enqueue_lead(conn, "account:"+user_id, email, "account_created", marketing_consent=checked(data.get("marketing")))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This account cannot be created. Try signing in or using your recovery key.") from None
    response = JSONResponse({"ok": True, "recovery_key": recovery, "next_url": safe_next(data.get("next"))}, status_code=201)
    start_session(response, user_id)
    background.add_task(flush_leads)
    return response


@router.post("/api/account/login")
async def login(request: Request):
    data = await read_input(request)
    email = email_address(data.get("email"))
    auth_limit(request, email)
    password = data.get("password")
    if not isinstance(password, str) or len(password) > 128:
        raise HTTPException(400, "Check your email and password.")
    with database() as conn:
        row = conn.execute("SELECT id,password_hash FROM users WHERE email=?", (email,)).fetchone()
    async with hash_slots:
        matched = await run_in_threadpool(password_matches, password, row["password_hash"] if row else DUMMY_HASH)
    if not row or not matched:
        raise HTTPException(400, "Check your email and password.")
    response = JSONResponse({"ok": True, "next_url": safe_next(data.get("next"))})
    start_session(response, row["id"])
    return response


@router.post("/api/account/recover")
async def recover(request: Request):
    data = await read_input(request)
    email = email_address(data.get("email"))
    auth_limit(request, email)
    password = validate_password(data.get("password"))
    key = data.get("recovery_key", "")
    if not isinstance(key, str) or len(key) > 100:
        raise HTTPException(400, "Check your email and recovery key.")
    with database() as conn:
        row = conn.execute("SELECT id,recovery_hash FROM users WHERE email=?", (email,)).fetchone()
    if not row or not hmac.compare_digest(row["recovery_hash"], digest(key.strip())):
        raise HTTPException(400, "Check your email and recovery key.")
    async with hash_slots:
        hashed = await run_in_threadpool(password_hash, password)
    recovery = secrets.token_urlsafe(32)
    with database(write=True) as conn:
        changed = conn.execute("UPDATE users SET password_hash=?,recovery_hash=? WHERE id=? AND recovery_hash=?",
                               (hashed, digest(recovery), row["id"], row["recovery_hash"]))
        if changed.rowcount != 1:
            raise HTTPException(400, "This recovery key has already been used.")
        conn.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    response = JSONResponse({"ok": True, "recovery_key": recovery, "next_url": "/account"})
    start_session(response, row["id"])
    return response


@router.post("/api/account/logout")
async def logout(request: Request):
    await read_input(request)
    with database(write=True) as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest(request.cookies.get(session_cookie(), "")),))
    response = JSONResponse({"ok": True, "next_url": "/"})
    response.delete_cookie(session_cookie(), path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(csrf_cookie(), path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")
    return response


@router.post("/api/account/preferences")
async def preferences(request: Request, background: BackgroundTasks):
    user = require_user(request)
    data = await read_input(request)
    marketing = checked(data.get("marketing"))
    with database(write=True) as conn:
        conn.execute("UPDATE users SET marketing=? WHERE id=?", (int(marketing), user["id"]))
        enqueue_lead(conn, "preference:"+secrets.token_hex(16), user["email"], "preferences_updated", marketing_consent=marketing)
    background.add_task(flush_leads)
    return {"ok": True, "message": "Your preference has been saved."}


@router.get("/api/saved")
async def saved_properties(request: Request):
    from zorbeck_app.catalog import public_properties
    user = user_for(request)
    with database() as conn:
        rows = conn.execute("SELECT property_id FROM saved WHERE user_id=?", (user["id"],)).fetchall() if user else []
    valid = {p["id"] for p in public_properties()}
    return JSONResponse({"authenticated": bool(user), "ids": [r[0] for r in rows if r[0] in valid]}, headers={"Cache-Control": "no-store"})


@router.post("/api/saved")
async def save_properties(request: Request):
    from zorbeck_app.catalog import public_properties
    user = require_user(request)
    data = await read_input(request)
    ids = data.get("ids")
    valid = {p["id"] for p in public_properties()}
    if not isinstance(ids, list) or len(ids) > 100 or any(not isinstance(x, str) or x not in valid for x in ids):
        raise HTTPException(400, "Choose properties from the current collection.")
    with database(write=True) as conn:
        conn.execute("DELETE FROM saved WHERE user_id=?", (user["id"],))
        conn.executemany("INSERT OR IGNORE INTO saved VALUES (?,?)", [(user["id"], x) for x in ids])
    return {"ok": True}


@router.get("/admin/claim")
async def claim_page(request: Request):
    if not user_for(request):
        return RedirectResponse("/login?next=/admin/claim", 303)
    return account_page(request, "market-claim.html")


@router.post("/api/admin/claim")
async def claim_admin(request: Request):
    user = require_user(request)
    data = await read_input(request)
    rate_limit("claim:"+user["id"], 5, 3600)
    token = data.get("token", "")
    if not settings.admin_bootstrap_hash or not isinstance(token, str) or len(token) > 100 or not hmac.compare_digest(
        digest(token), settings.admin_bootstrap_hash
    ):
        raise HTTPException(403, "This owner setup key is invalid.")
    with database(write=True) as conn:
        if conn.execute("SELECT value FROM app_meta WHERE key='admin_claimed'").fetchone():
            raise HTTPException(409, "Owner access has already been assigned.")
        conn.execute("INSERT INTO app_meta VALUES ('admin_claimed',?)", (user["id"],))
        conn.execute("UPDATE users SET role='admin' WHERE id=?", (user["id"],))
    return {"ok": True, "next_url": "/admin"}
