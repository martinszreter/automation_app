"""Public pages: landing, legal, health, robots — and the de-CH copy rules."""

import re

import pytest
from httpx import ASGITransport, AsyncClient

from zorbeck_app.config import settings
from zorbeck_app.main import app

PAGES = ("/", "/impressum", "/agb", "/datenschutz")
IMPRINT = ("STARTEND GmbH", "CHE-223.488.613", "Bahnhofstrasse 7", "6330 Cham", "info@startend.ch")
LEGAL_LINKS = ('href="/impressum"', 'href="/agb"', 'href="/datenschutz"')


def client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_landing_sells_one_offer_with_one_cta() -> None:
    async with client() as c:
        response = await c.get("/")
    assert response.status_code == 200
    assert 'lang="de-CH"' in response.text
    assert response.text.count("<h1") == 1
    assert response.text.count('type="submit"') == 1
    assert 'data-testid="cta"' in response.text
    assert "CHF 49" in response.text
    assert 'action="/checkout"' in response.text


@pytest.mark.asyncio
async def test_landing_states_the_offer_once_with_five_faq_answers() -> None:
    async with client() as c:
        text = (await c.get("/")).text
    # One offer block, one price, one CTA — nothing competes with the form.
    assert text.count('data-testid="offer"') == 1
    assert text.count('data-testid="price"') == 1
    assert text.count("<button") == 1
    assert text.count("<form") == 1
    # The three parts of the offer are stated before the form.
    for part in ("24 Stunden", "30 Tage", "endet automatisch"):
        assert part in text
    # Exactly five questions, each with an answer.
    faq = text.split('data-testid="faq"')[1]
    assert faq.count("<dt>") == 5
    assert faq.count("<dd>") == 5
    for question in (
        "Was genau bekomme ich?",
        "Woher stammen die Inserate",
        "Wie schnell kommt der erste Report?",
        "Was kostet es, und gibt es ein Abo?",
        "Was, wenn kein Report kommt?",
    ):
        assert question in faq, question
    # The FAQ names the same price as the offer, and the refund promise.
    assert "Einmalig CHF 49" in faq
    assert "vollen Betrag" in faq
    assert 'href="/agb"' in faq


@pytest.mark.asyncio
async def test_landing_price_comes_from_the_environment(monkeypatch) -> None:
    monkeypatch.setattr(settings, "price_cents", 100)
    async with client() as c:
        response = await c.get("/")
    assert "CHF 1<" in response.text or "CHF 1 " in response.text
    assert "CHF 49" not in response.text


@pytest.mark.asyncio
async def test_head_on_landing_is_200_not_a_redirect() -> None:
    async with client() as c:
        response = await c.head("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cancelled_checkout_lands_back_with_a_notice() -> None:
    async with client() as c:
        response = await c.get("/?abgebrochen=1")
    assert response.status_code == 200
    assert "abgebrochen" in response.text


@pytest.mark.parametrize("path", PAGES)
@pytest.mark.asyncio
async def test_every_page_carries_imprint_and_legal_links(path: str) -> None:
    async with client() as c:
        response = await c.get(path)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    for fragment in IMPRINT:
        assert fragment in response.text, f"{path} lacks {fragment}"
    for link in LEGAL_LINKS:
        assert link in response.text, f"{path} lacks {link}"
    assert "Keine Cookies" in response.text


@pytest.mark.asyncio
async def test_legal_pages_have_their_own_headline() -> None:
    async with client() as c:
        impressum = (await c.get("/impressum")).text
        agb = (await c.get("/agb")).text
        datenschutz = (await c.get("/datenschutz")).text
    assert "<h1>Impressum</h1>" in impressum
    assert "Allgemeine Geschäftsbedingungen" in agb
    assert "Rückerstattung" in agb
    assert "<h1>Datenschutz</h1>" in datenschutz
    assert "keine Cookies" in datenschutz


@pytest.mark.parametrize("path", PAGES)
@pytest.mark.asyncio
async def test_copy_is_de_ch_and_formal(path: str) -> None:
    async with client() as c:
        text = (await c.get(path)).text
    assert "ß" not in text, "de-CH writes ss, never ß"
    assert not re.search(r"\bCHF\s\d{1,3},\d{3}", text), "thousands use an apostrophe: CHF 1'390"
    assert not re.search(r"\b(Du|Dein|Deine|Dir|Dich)\b", text), "guests are addressed as Sie"
    for claim in ("besser als", "günstiger als", "schneller als", "Marktführer", "Nr. 1", "Konkurrenz", "Mitbewerber"):
        assert claim not in text, f"no comparative claims: {claim}"
    for buzzword in ("KI-gestützt", "revolutionär", "disruptiv", "Game-Changer", "smart", "innovativ"):
        assert buzzword.lower() not in text.lower(), f"plain words only: {buzzword}"
    assert "Szreter" not in text and "Gründer" not in text, "never the founder's background"
    if path != "/impressum":  # the imprint names the company, not the reader
        assert "Sie" in text or "Ihr" in text


@pytest.mark.asyncio
async def test_health_and_healthz_report_configuration_not_secrets(monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "secret-value-that-must-not-leak")
    monkeypatch.setattr(settings, "hq_mail_webhook_url", "")
    async with client() as c:
        health = await c.get("/health")
        healthz = await c.get("/healthz")
    assert health.status_code == healthz.status_code == 200
    body = healthz.json()
    assert body["ok"] is True
    assert body["service"] == "zorbeck"
    assert body["stripe"] is True
    assert body["mail"] is False
    assert body["stub"] is False
    assert "secret-value" not in healthz.text
    assert health.json() == body


@pytest.mark.asyncio
async def test_robots_allow_the_landing_and_hide_the_success_page() -> None:
    async with client() as c:
        response = await c.get("/robots.txt")
    assert response.status_code == 200
    assert "Allow: /" in response.text
    assert "Disallow: /danke" in response.text


@pytest.mark.asyncio
async def test_stub_is_not_mounted_unless_enabled() -> None:
    assert settings.stub is False
    async with client() as c:
        response = await c.post("/_stub/v1/checkout/sessions", content=b"mode=payment")
    assert response.status_code == 404
