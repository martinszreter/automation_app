"""Accounts, ownership boundaries and paid promotion. All external calls mocked."""
import base64
import io
import json
import secrets
import time
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from zorbeck_app import accounts
from zorbeck_app.catalog import public_properties
from zorbeck_app.config import settings
from zorbeck_app.main import app
from zorbeck_app.market_payments import process_event
from zorbeck_app.market_security import digest, password_matches, safe_next
from zorbeck_app.market_store import database, initialize
from zorbeck_app.stripe_api import sign_webhook_payload

PASSWORD = "a-long-unique-test-password"


@pytest.fixture(autouse=True)
def marketplace_config(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "marketplace_db_path", str(tmp_path / "market.sqlite3"))
    monkeypatch.setattr(settings, "cookie_secure", False)
    monkeypatch.setattr(settings, "public_base_url", "http://test")
    monkeypatch.setattr(settings, "stub", True)
    monkeypatch.setattr(settings, "signup_webhook_url", "")
    monkeypatch.setattr(settings, "admin_bootstrap_hash", digest("owner-setup-test-key"))
    monkeypatch.setattr(settings, "promotion_link", "https://buy.stripe.com/example")
    monkeypatch.setattr(settings, "promotion_link_id", "plink_promotion")
    monkeypatch.setattr(settings, "smoke_link", "https://buy.stripe.com/smoke")
    monkeypatch.setattr(settings, "smoke_link_id", "plink_smoke")
    monkeypatch.setattr(settings, "marketplace_webhook_secret", "local-signature-test-key")
    monkeypatch.setattr(accounts, "flush_leads", AsyncMock())
    initialize.cache_clear()
    yield
    initialize.cache_clear()


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def post(c, path, data, **kwargs):
    me = (await c.get("/api/me")).json()
    return await c.post(path, json=data, headers={"X-CSRF-Token": me["csrf"]}, **kwargs)


async def register(c, email="seller@example.com"):
    response = await post(c, "/api/account/register", {"email": email, "password": PASSWORD, "terms": True})
    assert response.status_code == 201, response.text
    return response.json()


async def photo(c):
    raw = io.BytesIO()
    Image.new("RGB", (64, 64), "ivory").save(raw, "JPEG", exif=b"Exif\x00\x00")
    response = await post(c, "/api/photos", {"content": base64.b64encode(raw.getvalue()).decode()})
    assert response.status_code == 200, response.text
    return response.json()["id"]


async def listing(c):
    photo_id = await photo(c)
    payload = {"title": "A home with a courtyard", "city": "Mussomeli", "country": "Italy", "type": "House",
               "currency": "EUR", "asking_price": "35000", "beds": "2", "area": "90", "lat": "37.58", "lng": "13.75",
               "description": "A seller-submitted home with two rooms and a courtyard. Arrange an independent viewing.",
               "seller_name": "Test owner", "seller_role": "Property owner", "photos": [photo_id],
               "authority": True, "photo_rights": True}
    response = await post(c, "/api/listings", payload)
    assert response.status_code == 200, response.text
    return response.json()["next_url"].split("/")[-1], payload


def paid_event(order_id, session="cs_test_example123456", event_id=None, **changes):
    obj = {"id": session, "client_reference_id": order_id, "payment_status": "paid", "mode": "payment",
           "livemode": False, "currency": "chf", "amount_total": 4900, "payment_link": "plink_promotion",
           "payment_intent": "pi_example123456", "metadata": {"venture": "zorbeck", "offering": "promotion"}, **changes}
    return {"id": event_id or "evt_"+secrets.token_hex(10), "type": "checkout.session.completed", "livemode": False, "data": {"object": obj}}


async def published_order(c):
    await register(c)
    listing_id, data = await listing(c)
    response = await post(c, f"/api/listings/{listing_id}/status", {"action": "submit"})
    assert response.status_code == 200
    await post(c, "/api/admin/claim", {"token": "owner-setup-test-key"})
    response = await post(c, f"/api/admin/listings/{listing_id}", {"action": "publish", "reviewed": True, "lat": 37.58, "lng": 13.75})
    assert response.status_code == 200, response.text
    response = await post(c, "/api/payments/start", {"listing_id": listing_id, "terms": True, "availability_confirmed": True})
    assert response.status_code == 200, response.text
    with database() as conn:
        order_id = conn.execute("SELECT id FROM orders WHERE kind='promotion'").fetchone()[0]
    return listing_id, order_id


@pytest.mark.asyncio
async def test_account_password_session_logout_and_single_use_recovery():
    async with client() as c:
        result = await register(c)
        me = (await c.get("/api/me")).json()
        assert me["user"]["email"] == "seller@example.com" and me["user"]["role"] == "member"
        with database() as conn:
            user = conn.execute("SELECT * FROM users").fetchone()
            session = conn.execute("SELECT * FROM sessions").fetchone()
            assert user["password_hash"] != PASSWORD and password_matches(PASSWORD, user["password_hash"])
            assert user["recovery_hash"] != result["recovery_key"]
            assert session["token_hash"] != c.cookies.get("zorbeck-session")
        stolen_old_session = c.cookies.get("zorbeck-session")
        response = await post(c, "/api/account/recover", {"email": user["email"], "recovery_key": result["recovery_key"], "password": "a-new-unique-test-password"})
        assert response.status_code == 200 and response.json()["recovery_key"] != result["recovery_key"]
        assert (await post(c, "/api/account/recover", {"email": user["email"], "recovery_key": result["recovery_key"], "password": PASSWORD})).status_code == 400
        async with client() as old:
            old.cookies.set("zorbeck-session", stolen_old_session)
            assert (await old.get("/api/me")).json()["user"] is None
        await post(c, "/api/account/logout", {})
        assert (await c.get("/api/me")).json()["user"] is None
        assert (await post(c, "/api/account/login", {"email": user["email"], "password": PASSWORD})).status_code == 400
        assert (await post(c, "/api/account/login", {"email": user["email"], "password": "a-new-unique-test-password"})).status_code == 200


@pytest.mark.asyncio
async def test_csrf_cross_origin_and_untrusted_next_are_rejected():
    assert safe_next("//evil.example") == safe_next("/\\evil.example") == safe_next("https://evil.example") == "/account"
    assert safe_next("/properties/jp-naka-1-33") == "/properties/jp-naka-1-33"
    async with client() as c:
        payload = {"email": "test@example.com", "password": PASSWORD, "terms": True}
        assert (await c.post("/api/account/register", json=payload)).status_code == 403
        token = (await c.get("/api/me")).json()["csrf"]
        assert (await c.post("/api/account/register", json=payload, headers={"X-CSRF-Token": token,"Origin":"https://evil.example"})).status_code == 403


@pytest.mark.asyncio
async def test_private_drafts_and_photos_cannot_be_read_or_changed_by_another_account():
    async with client() as owner, client() as other:
        await register(owner)
        listing_id, data = await listing(owner)
        await register(other, "other@example.com")
        assert (await other.get(f"/properties/{listing_id}")).status_code == 404
        assert (await other.get(f"/seller/properties/{listing_id}")).status_code == 404
        assert (await other.get("/media/"+data["photos"][0])).status_code == 404
        assert (await post(other, f"/api/listings/{listing_id}", data)).status_code == 404
        assert (await post(other, "/api/listings", data)).status_code == 400
        assert (await post(other, f"/api/admin/listings/{listing_id}", {"action":"publish"})).status_code == 403
        assert (await owner.get(f"/seller/properties/{listing_id}")).status_code == 200
        image = await owner.get("/media/"+data["photos"][0])
        assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
        assert not Image.open(io.BytesIO(image.content)).getexif()


@pytest.mark.asyncio
async def test_only_reviewed_publication_can_be_paid_and_ownership_is_checked():
    async with client() as c, client() as other:
        await register(c)
        listing_id, _ = await listing(c)
        assert (await post(c, "/api/payments/start", {"listing_id":listing_id,"terms":True})).status_code == 409
        assert (await post(c, f"/api/listings/{listing_id}/status", {"action":"submit"})).status_code == 200
        await register(other, "another@example.com")
        assert (await post(other, "/api/payments/start", {"listing_id":listing_id,"terms":True})).status_code == 404
        assert (await post(other, "/api/payments/start", {"kind":"smoke","terms":True})).status_code == 403
        assert (await post(c, "/api/admin/claim", {"token":"owner-setup-test-key"})).status_code == 200
        assert (await post(other, "/api/admin/claim", {"token":"owner-setup-test-key"})).status_code == 409
        assert (await post(c, f"/api/admin/listings/{listing_id}", {"action":"publish","lat":37.58,"lng":13.75})).status_code == 409
        assert (await post(c, f"/api/admin/listings/{listing_id}", {"action":"publish","reviewed":True,"lat":37.58,"lng":13.75})).status_code == 200
        assert (await c.get(f"/properties/{listing_id}")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"payment_status":"unpaid","status":"complete"}, {"amount_total":1}, {"currency":"eur"},
                                  {"payment_link":"plink_other"}, {"metadata":{"venture":"other","offering":"promotion"}}, {"livemode":True}])
async def test_mismatched_or_unpaid_sessions_cannot_feature_a_property(change):
    async with client() as c:
        listing_id, order_id = await published_order(c)
        process_event(paid_event(order_id, **change))
        assert not next(p for p in public_properties() if p["id"] == listing_id)["featured"]
        with database() as conn:
            assert conn.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()[0] == "pending"


@pytest.mark.asyncio
async def test_signed_payment_activates_once_and_refund_revokes_even_out_of_order():
    async with client() as c:
        listing_id, order_id = await published_order(c)
        event = paid_event(order_id)
        payload = json.dumps(event).encode()
        assert (await c.post("/api/marketplace/stripe", content=payload, headers={"Stripe-Signature":"bad"})).status_code == 400
        # A fabricated return page never grants anything.
        assert (await c.get("/payments/return?session_id=cs_test_example123456")).status_code == 200
        assert not next(p for p in public_properties() if p["id"] == listing_id)["featured"]
        signature = sign_webhook_payload(payload, settings.marketplace_webhook_secret)
        response = await c.post("/api/marketplace/stripe", content=payload, headers={"Stripe-Signature":signature})
        assert response.status_code == 200
        assert next(p for p in public_properties() if p["id"] == listing_id)["featured"]
        with database() as conn:
            until = conn.execute("SELECT promotion_until FROM orders WHERE id=?", (order_id,)).fetchone()[0]
        assert 29*86400 < until-time.time() <= 30*86400
        process_event(event)
        process_event(paid_event(order_id))
        with database() as conn:
            assert conn.execute("SELECT promotion_until FROM orders WHERE id=?", (order_id,)).fetchone()[0] == until
        refund = {"id":"evt_refund1", "type":"charge.refunded", "livemode":False,"data":{"object":{"payment_intent":"pi_example123456"}}}
        process_event(refund)
        assert not next(p for p in public_properties() if p["id"] == listing_id)["featured"]
        process_event(paid_event(order_id))
        assert not next(p for p in public_properties() if p["id"] == listing_id)["featured"]


@pytest.mark.asyncio
async def test_refund_before_checkout_and_duplicate_purchase_never_grant_extra_time():
    async with client() as c:
        listing_id, order_id = await published_order(c)
        process_event({"id":"evt_earlyrefund", "type":"charge.refunded", "livemode":False,"data":{"object":{"payment_intent":"pi_example123456"}}})
        process_event(paid_event(order_id))
        process_event(paid_event(order_id, session="cs_test_duplicate123456", payment_intent="pi_second123456"))
        with database() as conn:
            assert conn.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()[0] == "refunded"
            assert conn.execute("SELECT COUNT(*) FROM payment_exceptions").fetchone()[0] == 1
        assert not next(p for p in public_properties() if p["id"] == listing_id)["featured"]


@pytest.mark.asyncio
async def test_buyer_enquiry_requires_consent_and_is_visible_only_to_seller():
    async with client() as owner, client() as buyer, client() as stranger:
        listing_id, _ = await published_order(owner)
        await register(buyer, "buyer@example.com")
        await register(stranger, "stranger@example.com")
        payload = {"message":"Could we arrange an independent viewing of the property?"}
        assert (await post(buyer, f"/api/enquiries/{listing_id}", payload)).status_code == 400
        assert (await post(buyer, f"/api/enquiries/{listing_id}", {**payload,"share_email":True})).status_code == 200
        assert payload["message"] in (await owner.get("/account")).text
        assert payload["message"] not in (await stranger.get("/account")).text


@pytest.mark.asyncio
async def test_advertisement_content_is_escaped_and_source_collection_can_be_hidden():
    async with client() as c:
        await register(c)
        listing_id, data = await listing(c)
        data["title"] = '<img src=x onerror="alert(1)">'
        assert (await post(c, f"/api/listings/{listing_id}", data)).status_code == 200
        page = await c.get(f"/seller/properties/{listing_id}")
        assert '<img src=x onerror=' not in page.text and '&lt;img' in page.text
        await post(c, "/api/admin/claim", {"token":"owner-setup-test-key"})
        assert (await post(c, "/api/admin/sources/jp-naka-1-33", {"action":"hide"})).status_code == 200
        assert not any(p["id"] == "jp-naka-1-33" for p in public_properties())


@pytest.mark.asyncio
async def test_signed_in_saved_properties_are_private_and_persist_in_database():
    async with client() as first, client() as second:
        await register(first)
        await register(second, "second@example.com")
        assert (await post(first, "/api/saved", {"ids":["jp-naka-1-33"]})).status_code == 200
        assert (await first.get("/api/saved")).json()["ids"] == ["jp-naka-1-33"]
        assert (await second.get("/api/saved")).json()["ids"] == []
        assert (await post(first, "/api/saved", {"ids":["fake-property"]})).status_code == 400
        assert (await first.get("/account")).headers["cache-control"] == "private, no-store"
