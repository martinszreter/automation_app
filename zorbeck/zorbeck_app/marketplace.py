"""Seller drafts, moderation, original photos and private buyer enquiries."""
from __future__ import annotations

import base64
import io
import json
import math
import re
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from zorbeck_app.accounts import account_page, checked, flush_leads
from zorbeck_app.catalog import COUNTRIES, SOURCED, decorate, find_public, public_properties
from zorbeck_app.market_payments import configured
from zorbeck_app.market_security import read_input, require_admin, require_user, user_for
from zorbeck_app.market_store import database, enqueue_lead, rate_limit

router = APIRouter()
Image.MAX_IMAGE_PIXELS = 16_000_000
CURRENCIES = ["EUR", "CHF", "USD", "GBP", "JPY", "CNY", "THB", "AUD", "CAD", "SGD", "AED", "IDR", "PLN"]


def text_field(data, name, minimum=0, maximum=200):
    value = data.get(name, "")
    if not isinstance(value, str):
        raise HTTPException(400, f"Please check {name.replace('_', ' ')}.")
    value = value.strip()
    if not minimum <= len(value) <= maximum or any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise HTTPException(400, f"Use {minimum}–{maximum} characters for {name.replace('_', ' ')}.")
    return value


def number_field(data, name, minimum, maximum, optional=False):
    value = data.get(name)
    if optional and value in (None, ""):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        raise HTTPException(400, f"Enter a valid {name.replace('_', ' ')}.") from None
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise HTTPException(400, f"Check the {name.replace('_', ' ')} range.")
    return value


def listing_data(data):
    country = text_field(data, "country", 2, 80)
    kind = text_field(data, "type", 3, 20)
    currency = text_field(data, "currency", 3, 3)
    if country not in COUNTRIES or kind not in {"House", "Apartment", "Villa", "Land", "Commercial"} or currency not in CURRENCIES:
        raise HTTPException(400, "Choose a country, property type and currency from the list.")
    if data.get("seller_role") not in {"Property owner", "Authorised agent"}:
        raise HTTPException(400, "Choose your role as owner or authorised agent.")
    source = text_field(data, "source_url", 0, 600)
    if source:
        url = urlsplit(source)
        if url.scheme != "https" or not url.hostname or url.username or url.password or any(c.isspace() for c in source):
            raise HTTPException(400, "Use a complete https:// property reference link, or leave it empty.")
    photos = data.get("photos", [])
    if isinstance(photos, str):
        try:
            photos = json.loads(photos)
        except ValueError:
            photos = []
    if not isinstance(photos, list) or len(photos) > 3 or any(not isinstance(p, str) or not re.fullmatch(r"[a-f0-9]{32}", p) for p in photos):
        raise HTTPException(400, "Upload up to three property photographs.")
    if len(set(photos)) != len(photos):
        raise HTTPException(400, "Each photograph can be selected once.")
    if not checked(data.get("authority")) or not checked(data.get("photo_rights")):
        raise HTTPException(400, "Confirm your authority to advertise and your rights to the submitted content.")
    return {
        "title": text_field(data, "title", 8, 100), "city": text_field(data, "city", 2, 80),
        "country": country, "region": "Worldwide", "type": kind, "currency": currency,
        "asking_price": number_field(data, "asking_price", 1, 100_000_000_000),
        "beds": number_field(data, "beds", 0, 100, True), "area": number_field(data, "area", 1, 1_000_000, True),
        "land_area": number_field(data, "land_area", 1, 100_000_000, True),
        "lat": number_field(data, "lat", -85, 85, True), "lng": number_field(data, "lng", -180, 180, True),
        "description": text_field(data, "description", 40, 2500),
        "neighborhood": text_field(data, "neighborhood", 0, 120),
        "seller_name": text_field(data, "seller_name", 2, 100),
        "seller_role": text_field(data, "seller_role", 4, 40),
        "reference_url": source, "photos": photos, "tag": "Direct from seller",
        "authority": True, "photo_rights": True,
        "distribution_consent": checked(data.get("distribution_consent")),
    }


def owned_listing(listing_id, user):
    with database() as conn:
        row = conn.execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "This property is not in your account.")
    return dict(row)


@router.get("/sell")
async def sell(request: Request):
    return account_page(request, "market-sell.html")


@router.get("/terms/marketplace")
async def market_terms(request: Request):
    return account_page(request, "market-terms.html")


@router.get("/sell/new")
async def new_listing(request: Request):
    if not user_for(request):
        return RedirectResponse("/register?next=/sell/new", 303)
    return account_page(request, "market-listing-form.html", listing=None, values={}, countries=COUNTRIES, currencies=CURRENCIES)


@router.get("/sell/{listing_id}/edit")
async def edit_listing(request: Request, listing_id: str):
    user = require_user(request)
    row = owned_listing(listing_id, user)
    return account_page(request, "market-listing-form.html", listing=row, values=json.loads(row["data_json"]),
                        countries=COUNTRIES, currencies=CURRENCIES)


@router.get("/seller/properties/{listing_id}")
async def preview_listing(request: Request, listing_id: str):
    user = require_user(request)
    row = owned_listing(listing_id, user)
    item = json.loads(row["data_json"])
    item.update(id=listing_id, kind="seller", source_checked=datetime.now(timezone.utc).date().isoformat(),
                source_name="Your submission", source_url="", source_updated=None, considerations=[])
    return account_page(request, "market-property.html", property=decorate(item), listing=row, draft_preview=True)


@router.get("/account")
async def account(request: Request, background: BackgroundTasks):
    user = user_for(request)
    if not user:
        return RedirectResponse("/login", 303)
    with database() as conn:
        listings = [dict(r) for r in conn.execute("SELECT * FROM listings WHERE owner_id=? ORDER BY created_at DESC", (user["id"],))]
        enquiries = [dict(r) for r in conn.execute(
            "SELECT e.*,u.email AS buyer_email,l.data_json FROM enquiries e JOIN listings l ON l.id=e.listing_id "
            "JOIN users u ON u.id=e.buyer_id WHERE l.owner_id=? ORDER BY e.created_at DESC LIMIT 100", (user["id"],))]
        orders = [dict(r) for r in conn.execute("SELECT o.*,l.status AS listing_status FROM orders o LEFT JOIN listings l ON l.id=o.listing_id WHERE o.user_id=? ORDER BY o.created_at DESC LIMIT 100", (user["id"],))]
        saved = {r[0] for r in conn.execute("SELECT property_id FROM saved WHERE user_id=?", (user["id"],))}
    for row in listings + enquiries:
        row["property"] = json.loads(row["data_json"])
    background.add_task(flush_leads)
    return account_page(request, "market-account.html", listings=listings, enquiries=enquiries, orders=orders,
                        shortlist=[p for p in public_properties() if p["id"] in saved], now=int(time.time()))


@router.post("/api/listings")
@router.post("/api/listings/{listing_id}")
async def save_listing(request: Request, background: BackgroundTasks, listing_id: str = ""):
    user = require_user(request)
    data = await read_input(request)
    rate_limit("listing-save:"+user["id"], 40, 3600)
    item = listing_data(data)
    now = int(time.time())
    with database(write=True) as conn:
        if listing_id:
            row = conn.execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
            if not row:
                raise HTTPException(404, "This property is not in your account.")
            active = conn.execute("SELECT id FROM orders WHERE listing_id=? AND status='paid' AND promotion_until>?",
                                  (listing_id, now)).fetchone()
            if active:
                raise HTTPException(409, "This property is featured. Contact support for corrections; you can still mark it sold or withdraw it.")
        else:
            if conn.execute("SELECT COUNT(*) FROM listings WHERE owner_id=?", (user["id"],)).fetchone()[0] >= 20:
                raise HTTPException(409, "Your account has reached 20 submissions. Contact us for agency access.")
            listing_id = "seller-"+secrets.token_hex(16)
        for photo_id in item["photos"]:
            photo = conn.execute("SELECT owner_id,listing_id FROM photos WHERE id=?", (photo_id,)).fetchone()
            if not photo or photo["owner_id"] != user["id"] or photo["listing_id"] not in {None, listing_id}:
                raise HTTPException(400, "Choose photographs uploaded for this property by your account.")
        if conn.execute("SELECT id FROM listings WHERE id=?", (listing_id,)).fetchone():
            conn.execute("UPDATE listings SET data_json=?,status='draft',updated_at=?,review_note='' WHERE id=?",
                         (json.dumps(item), now, listing_id))
        else:
            conn.execute("INSERT INTO listings(id,owner_id,data_json,created_at,updated_at) VALUES (?,?,?,?,?)",
                         (listing_id, user["id"], json.dumps(item), now, now))
            enqueue_lead(conn, "seller:"+listing_id, user["email"], "seller_draft", property_id=listing_id,
                         city=item["city"], country=item["country"], marketing_consent=bool(user["marketing"]))
        conn.execute("UPDATE photos SET listing_id=NULL WHERE listing_id=?", (listing_id,))
        for photo_id in item["photos"]:
            conn.execute("UPDATE photos SET listing_id=? WHERE id=?", (listing_id, photo_id))
    background.add_task(flush_leads)
    return {"ok": True, "next_url": f"/seller/properties/{listing_id}"}


@router.post("/api/listings/{listing_id}/status")
async def listing_status(request: Request, listing_id: str):
    user = require_user(request)
    data = await read_input(request)
    action = data.get("action")
    if action not in {"submit", "withdraw", "sold"}:
        raise HTTPException(400, "Choose a valid property action.")
    with database(write=True) as conn:
        row = conn.execute("SELECT * FROM listings WHERE id=? AND owner_id=?", (listing_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(404, "This property is not in your account.")
        item = json.loads(row["data_json"])
        if action == "submit":
            if row["status"] not in {"draft", "rejected"}:
                raise HTTPException(409, "This property has already been submitted.")
            if not item["photos"]:
                raise HTTPException(400, "Add at least one photograph before submitting.")
        status = {"submit": "pending", "withdraw": "withdrawn", "sold": "sold"}[action]
        conn.execute("UPDATE listings SET status=?,updated_at=? WHERE id=?", (status, int(time.time()), listing_id))
    return {"ok": True, "next_url": "/account"}


def clean_photo(encoded):
    if not isinstance(encoded, str) or len(encoded) > 4_200_000:
        raise HTTPException(400, "Choose a JPEG, PNG or WebP photo under 3 MB.")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 3_000_000:
            raise ValueError("size")
        with Image.open(io.BytesIO(raw)) as original:
            if original.format not in {"JPEG", "PNG", "WEBP"} or original.width*original.height > 16_000_000:
                raise ValueError("format")
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((1600, 1600))
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=85, optimize=True)
            return output.getvalue()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "The photo could not be processed. Use a JPEG, PNG or WebP under 3 MB and 16 megapixels.") from None


@router.post("/api/photos")
async def upload_photo(request: Request):
    user = require_user(request)
    data = await read_input(request, limit=4_250_000)
    rate_limit("photo:"+user["id"], 30, 3600)
    content = await run_in_threadpool(clean_photo, data.get("content"))
    photo_id = secrets.token_hex(16)
    with database(write=True) as conn:
        conn.execute("DELETE FROM photos WHERE listing_id IS NULL AND created_at<?", (int(time.time())-86400,))
        if conn.execute("SELECT COUNT(*) FROM photos WHERE owner_id=?", (user["id"],)).fetchone()[0] >= 60:
            raise HTTPException(409, "Your photo allowance is full. Remove unused drafts or contact support.")
        conn.execute("INSERT INTO photos VALUES (?,?,NULL,?,?)", (photo_id, user["id"], content, int(time.time())))
    return {"ok": True, "id": photo_id, "url": "/media/"+photo_id}


@router.get("/media/{photo_id}")
async def photo(request: Request, photo_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}", photo_id):
        raise HTTPException(404, "Photograph not found.")
    with database() as conn:
        row = conn.execute("SELECT p.*,l.status FROM photos p LEFT JOIN listings l ON l.id=p.listing_id WHERE p.id=?", (photo_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Photograph not found.")
    public = row["status"] == "published"
    user = user_for(request)
    if not public and (not user or (row["owner_id"] != user["id"] and user["role"] != "admin")):
        raise HTTPException(404, "Photograph not found.")
    return Response(row["content"], media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff",
                    "Cache-Control": "public, max-age=300" if public else "private, no-store"})


@router.post("/api/enquiries/{listing_id}")
async def enquiry(request: Request, listing_id: str, background: BackgroundTasks):
    user = require_user(request)
    data = await read_input(request)
    rate_limit("enquiry:"+user["id"], 10, 3600)
    message = text_field(data, "message", 20, 2000)
    if not checked(data.get("share_email")):
        raise HTTPException(400, "Confirm that this seller may see your email and enquiry.")
    if not find_public(listing_id) or not listing_id.startswith("seller-"):
        raise HTTPException(404, "Use the original advertiser's contact route for this property.")
    enquiry_id = secrets.token_hex(16)
    with database(write=True) as conn:
        listing = conn.execute("SELECT owner_id FROM listings WHERE id=? AND status='published'", (listing_id,)).fetchone()
        if not listing or listing["owner_id"] == user["id"]:
            raise HTTPException(400, "You cannot send this enquiry.")
        conn.execute("INSERT INTO enquiries VALUES (?,?,?,?,?)", (enquiry_id, listing_id, user["id"], message, int(time.time())))
        enqueue_lead(conn, "enquiry:"+enquiry_id, user["email"], "buyer_enquiry", property_id=listing_id,
                     marketing_consent=bool(user["marketing"]), seller_contact_consent=True)
    background.add_task(flush_leads)
    return {"ok": True, "message": "Your enquiry is in the seller’s Zorbeck inbox. They can reply to your email."}


@router.get("/admin")
async def admin(request: Request, background: BackgroundTasks):
    if not user_for(request):
        return RedirectResponse("/login?next=/admin", 303)
    require_admin(request)
    with database() as conn:
        rows = [dict(r) for r in conn.execute("SELECT l.*,u.email FROM listings l JOIN users u ON u.id=l.owner_id "
                                             "ORDER BY CASE l.status WHEN 'pending' THEN 0 ELSE 1 END,l.created_at DESC LIMIT 200")]
        stats = {"accounts": conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
                 "pending": conn.execute("SELECT COUNT(*) FROM listings WHERE status='pending'").fetchone()[0],
                 "revenue": conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM orders WHERE status='paid' AND kind='promotion'").fetchone()[0],
                 "unsynced": conn.execute("SELECT COUNT(*) FROM lead_outbox WHERE delivered_at IS NULL").fetchone()[0]}
        exceptions = [dict(r) for r in conn.execute("SELECT * FROM payment_exceptions ORDER BY created_at DESC LIMIT 50")]
        leads = [dict(r) for r in conn.execute("SELECT email,marketing,created_at FROM users ORDER BY created_at DESC LIMIT 100")]
    for row in rows:
        row["property"] = json.loads(row["data_json"])
    background.add_task(flush_leads)
    return account_page(request, "market-admin.html", listings=rows, stats=stats, exceptions=exceptions,
                        leads=leads, sources=SOURCED, smoke_ready=configured("smoke"))


@router.post("/api/admin/listings/{listing_id}")
async def review_listing(request: Request, listing_id: str):
    user = require_admin(request)
    data = await read_input(request)
    action = data.get("action")
    if action not in {"publish", "reject", "withdraw"}:
        raise HTTPException(400, "Choose a valid review action.")
    note = text_field(data, "note", 0 if action == "publish" else 10, 1000)
    now = int(time.time())
    with database(write=True) as conn:
        row = conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Property not found.")
        item = json.loads(row["data_json"])
        if action == "publish":
            if row["status"] not in {"pending", "rejected"} or not checked(data.get("reviewed")):
                raise HTTPException(409, "Review the submitted property and confirm the checks before publishing.")
            item["lat"] = number_field(data, "lat", -85, 85)
            item["lng"] = number_field(data, "lng", -180, 180)
            if not item["photos"] or not item["authority"] or not item["photo_rights"]:
                raise HTTPException(409, "Photos and advertising permissions are required.")
        status = {"publish": "published", "reject": "rejected", "withdraw": "withdrawn"}[action]
        conn.execute("UPDATE listings SET status=?,data_json=?,review_note=?,updated_at=?,published_at=? WHERE id=?",
                     (status, json.dumps(item), note, now, now if status == "published" else row["published_at"], listing_id))
        conn.execute("INSERT INTO moderation(listing_id,admin_id,action,note,created_at) VALUES (?,?,?,?,?)",
                     (listing_id, user["id"], action, note, now))
    return {"ok": True, "next_url": "/admin"}


@router.post("/api/admin/sources/{source_id}")
async def review_source(request: Request, source_id: str):
    user = require_admin(request)
    data = await read_input(request)
    if not any(s["id"] == source_id for s in SOURCED):
        raise HTTPException(404, "Source not found.")
    action = data.get("action")
    if action not in {"hide", "reviewed"} or (action == "reviewed" and not checked(data.get("reviewed"))):
        raise HTTPException(400, "Confirm that you checked the original advertisement.")
    value = {"hidden": action == "hide", "checked": datetime.now(timezone.utc).date().isoformat()}
    with database(write=True) as conn:
        conn.execute("INSERT OR REPLACE INTO app_meta VALUES (?,?)", ("source:"+source_id, json.dumps(value)))
        conn.execute("INSERT INTO moderation(listing_id,admin_id,action,note,created_at) VALUES (?,?,?,?,?)",
                     (source_id, user["id"], action, "Original source review", int(time.time())))
    return {"ok": True, "next_url": "/admin"}
