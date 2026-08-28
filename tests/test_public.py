import re

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import get_db


def _client_with_mock_db(mock_session: AsyncMock) -> AsyncClient:
    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_homepage_serves_index_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "No Human" in response.text
    assert "Bahnhofstrasse 7, 6330 Cham" in response.text
    assert "CHE-223.488.613" in response.text


@pytest.mark.asyncio
async def test_x_autopilot_landing_serves_index_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "X Autopilot" in response.text
    assert "322 posts in 30 days. Zero human touch." in response.text


@pytest.mark.asyncio
async def test_x_autopilot_onboarding_serves_onboarding_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot/onboarding.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Now let's capture your voice." in response.text


@pytest.mark.asyncio
async def test_x_autopilot_without_slash_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot")

    assert response.status_code == 301
    assert response.headers["location"] == "/x-autopilot/"


@pytest.mark.asyncio
async def test_x_autopilot_without_slash_redirects_on_head():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.head("/x-autopilot")

    assert response.status_code == 301
    assert response.headers["location"] == "/x-autopilot/"


@pytest.mark.asyncio
async def test_grokywood_landing_serves_index_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/grokywood/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Grokywood" in response.text


@pytest.mark.asyncio
async def test_grokywood_without_slash_redirects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/grokywood")

    assert response.status_code == 301
    assert response.headers["location"] == "/grokywood/"


@pytest.mark.asyncio
async def test_offer_pages_not_shadowed_by_generic_landing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bodies = [(await client.get(path)).text for path in ("/", "/x-autopilot/", "/grokywood/")]

    assert len(set(bodies)) == 3
    assert "CHF 149" in bodies[1]
    assert "Grokywood" in bodies[2]


@pytest.mark.asyncio
async def test_unknown_path_returns_404_without_redirect():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        without_slash = await client.get("/nonsense-404-test")
        with_slash = await client.get("/nonsense-404-test/")

    assert without_slash.status_code == 404
    assert with_slash.status_code == 404


@pytest.mark.asyncio
async def test_generic_landing_serves_canon_page_dirs(tmp_path, monkeypatch):
    """Pages the deploy drops under static/ (apps, agents, …) are served generically."""
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "index.html").write_text("<html>Business Apps</html>")
    monkeypatch.setattr("app.api.public._STATIC_DIR", tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/apps/")
        redirect = await client.get("/apps")

    assert page.status_code == 200
    assert "Business Apps" in page.text
    assert redirect.status_code == 301
    assert redirect.headers["location"] == "/apps/"


@pytest.mark.asyncio
async def test_favicon_serves_svg_with_long_cache():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "#DA291C" in response.text


@pytest.mark.asyncio
async def test_contact_stores_request_and_sends_email():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.api.public.send_contact_notification", new_callable=AsyncMock) as mock_notify:
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "Anna",
                    "company": "ACME AG",
                    "email": "anna@example.com",
                    "interest": "enterprise",
                    "message": "Hello",
                    "call_requested": "yes",
                    "website": "",
                },
            )

    assert response.status_code == 200
    assert "Thank you" in response.text
    mock_session.add.assert_called_once()
    stored = mock_session.add.call_args.args[0]
    assert stored.name == "Anna"
    assert stored.email == "anna@example.com"
    assert stored.call_requested is True
    mock_session.commit.assert_awaited_once()
    mock_notify.assert_awaited_once_with(stored)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_honeypot_skips_storage_and_email():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.api.public.send_contact_notification", new_callable=AsyncMock) as mock_notify:
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "Bot",
                    "email": "bot@spam.com",
                    "message": "spam",
                    "website": "http://spam.example",
                },
            )

    assert response.status_code == 200
    assert "Thank you" in response.text
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_awaited()
    mock_notify.assert_not_awaited()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_smtp_failure_still_stores_and_thanks():
    """Email must never break the form: SMTP errors are logged and swallowed."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    smtp_settings = {
        "smtp_host": "smtp.example.com",
        "smtp_user": "noreply@example.com",
        "smtp_pass": "secret",
        "contact_to": "inbox@example.com",
    }
    with (
        patch.multiple("app.services.contact_email.settings", **smtp_settings),
        patch(
            "app.services.contact_email._send_sync",
            side_effect=ConnectionRefusedError("SMTP down"),
        ),
    ):
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "Anna",
                    "email": "anna@example.com",
                    "message": "Hello",
                    "website": "",
                },
            )

    assert response.status_code == 200
    assert "Thank you" in response.text
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_contact_email_message_content():
    """The notification email carries all form fields."""
    from app.db.models import ContactRequest
    from app.services.contact_email import _build_message

    contact = ContactRequest(
        name="Anna",
        company="ACME AG",
        email="anna@example.com",
        interest="enterprise",
        message="Hello there",
        call_requested=True,
    )
    smtp_settings = {
        "smtp_user": "noreply@example.com",
        "contact_to": "inbox@example.com",
    }
    with patch.multiple("app.services.contact_email.settings", **smtp_settings):
        msg = _build_message(contact)

    assert msg["From"] == "noreply@example.com"
    assert msg["To"] == "inbox@example.com"
    assert msg["Subject"] == "New contact: Anna — enterprise"
    body = msg.get_content()
    for expected in ["Anna", "ACME AG", "anna@example.com", "enterprise", "yes", "Hello there"]:
        assert expected in body


@pytest.mark.asyncio
async def test_x_autopilot_landing_carries_exactly_one_price_and_one_stripe_link():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get("/x-autopilot/")).text

    # Exactly one amount anywhere on the page — no tiers, no setup variants.
    assert set(re.findall(r"CHF\s?[\d'.,]+", body)) == {"CHF 149"}
    for removed in ("330", "660", "990"):
        assert removed not in body
    # One Stripe target, and it is the placeholder Marcin fills in.
    assert "buy.stripe.com" not in body
    assert len(re.findall(r"https://buy\.", body)) == 0
    assert "STRIPE_XAUTOPILOT_149" in body
    # One offer button, one lead form.
    assert body.count('id="startBtn"') == 1
    assert body.count('action="/contact"') == 1


@pytest.mark.asyncio
async def test_x_autopilot_view_counter_records_utm():
    from app.api import public

    before = public._XA_STATS["views"]["total"]
    before_src = public._XA_STATS["views"]["utm_source"].get("x-ads", 0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot/?utm_source=x-ads&utm_campaign=launch")
        stats = await client.get("/x-autopilot/stats.json")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["views"]["total"] == before + 1
    assert payload["views"]["utm_source"]["x-ads"] == before_src + 1
    assert payload["views"]["utm_campaign"]["launch"] >= 1
    assert sum(payload["views"]["days"].values()) == payload["views"]["total"]


@pytest.mark.asyncio
async def test_x_autopilot_stats_json_is_not_indexable():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/x-autopilot/stats.json")

    assert response.status_code == 200
    assert "noindex" in response.headers["x-robots-tag"]
    for bucket in ("views", "stripe_clicks", "emails"):
        assert bucket in response.json()


@pytest.mark.asyncio
async def test_x_autopilot_stripe_click_is_counted_separately():
    from app.api import public

    before = public._XA_STATS["stripe_clicks"]["total"]
    before_views = public._XA_STATS["views"]["total"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/x-autopilot/event",
            data={"event": "stripe", "utm_source": "x-ads", "utm_campaign": "launch"},
        )
        unknown = await client.post("/x-autopilot/event", data={"event": "nonsense"})

    assert response.status_code == 204
    assert unknown.status_code == 404
    assert public._XA_STATS["stripe_clicks"]["total"] == before + 1
    assert public._XA_STATS["stripe_clicks"]["utm_source"]["x-ads"] >= 1
    assert public._XA_STATS["views"]["total"] == before_views


@pytest.mark.asyncio
async def test_teardown_lead_counts_as_email_on_shared_contact_endpoint():
    from app.api import public

    before = public._XA_STATS["emails"]["total"]
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.api.public.send_contact_notification", new_callable=AsyncMock):
        async with _client_with_mock_db(mock_session) as client:
            response = await client.post(
                "/contact",
                data={
                    "name": "X Autopilot teardown",
                    "email": "lead@example.com",
                    "interest": "x-autopilot-teardown",
                    "message": "Teardown request from /x-autopilot/",
                    "website": "",
                },
            )

    assert response.status_code == 200
    assert public._XA_STATS["emails"]["total"] == before + 1
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ordinary_contact_lead_does_not_count_as_x_autopilot_email():
    from app.api import public

    before = public._XA_STATS["emails"]["total"]
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.api.public.send_contact_notification", new_callable=AsyncMock):
        async with _client_with_mock_db(mock_session) as client:
            await client.post(
                "/contact",
                data={
                    "name": "Anna",
                    "email": "anna@example.com",
                    "interest": "enterprise",
                    "message": "Hello",
                    "website": "",
                },
            )

    assert public._XA_STATS["emails"]["total"] == before
    app.dependency_overrides.clear()
