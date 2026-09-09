"""User-facing discovery and registration; no real registration or email in tests."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from zorbeck_app.config import settings
from zorbeck_app.discovery import PROPERTIES, attempts
from zorbeck_app.main import app

BASE = Path(__file__).resolve().parent.parent
VALID = {"email": "example@example.com", "city": "Lisbon", "budget_max": "600000", "consent": True}


@pytest.fixture(autouse=True)
def clear_registration_limits():
    attempts.clear()
    yield
    attempts.clear()


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_homepage_is_honest_global_discovery_and_offer_remains_available():
    async with client() as c:
        home = await c.get("/")
        offer = await c.get("/deal-alarm")
        head = await c.head("/")
    assert home.status_code == offer.status_code == head.status_code == 200
    assert 'data-zorbeck-discovery="2026-09-09"' in home.text
    assert 'id="property-map"' in home.text
    assert 'id="register-form"' in home.text
    assert "Illustrative properties and prices, not active listings" in home.text
    assert "do not run a live AI search" in home.text
    assert "STARTEND GmbH" in home.text
    assert 'action="/checkout"' in offer.text
    assert 'action="/checkout"' not in home.text
    data = json.loads(home.text.split('id="property-data">')[1].split('</script>')[0])
    assert len(data) == 8
    for record in data:
        assert (BASE / 'static' / 'discovery' / record['image']).is_file()
        assert -90 <= record['lat'] <= 90 and -180 <= record['lng'] <= 180


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [{"email": "bad"}, {"consent": False}, {"city": ""}, {"budget_max": "-1"}, {"website": "spam"}])
async def test_invalid_registration_never_reaches_sink(change, monkeypatch):
    monkeypatch.setattr(settings, 'signup_webhook_url', 'https://sink.invalid/register')
    sink = AsyncMock()
    with patch('httpx.AsyncClient.post', sink):
        async with client() as c:
            response = await c.request('POST', '/api/early-access', json={**VALID, **change})
    assert response.status_code == 400
    sink.assert_not_awaited()


@pytest.mark.asyncio
async def test_registration_fails_honestly_without_persistence(monkeypatch):
    monkeypatch.setattr(settings, 'signup_webhook_url', '')
    async with client() as c:
        response = await c.post('/api/early-access', json=VALID)
    assert response.status_code == 503
    assert response.json()['ok'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('outcome', ['success', 'declined', 'offline'])
async def test_registration_acknowledges_sink_success_only(outcome, monkeypatch):
    monkeypatch.setattr(settings, 'signup_webhook_url', 'https://sink.invalid/register')
    receipt = httpx.Response(200, json={"ok": outcome == 'success'}, request=httpx.Request('POST', 'https://sink.invalid/register'))
    sink = AsyncMock(return_value=receipt)
    if outcome == 'offline':
        sink.side_effect = httpx.ConnectError('unavailable')
    with patch('httpx.AsyncClient.post', sink):
        async with client() as c:
            response = await c.request('POST', '/api/early-access', json=VALID)
    assert response.status_code == (201 if outcome == 'success' else 502)
    assert response.json()['ok'] is (outcome == 'success')
    payload = sink.await_args.kwargs['json']
    assert payload['status'] == 'early_access'
    assert payload['currency'] == 'EUR'
    assert payload['budget_max'] == 600000
    assert payload['consent_at']
    assert 'sink.invalid' not in response.text


@pytest.mark.asyncio
async def test_early_access_payload_size_limit_and_content_type():
    async with client() as c:
        large = await c.post('/api/early-access', json={**VALID, 'city': 'a' * 5000})
        plain = await c.post('/api/early-access', content=json.dumps(VALID))
    assert large.status_code == 413
    assert plain.status_code == 415


def test_sample_catalog_images_have_attribution_and_unique_ids():
    assert len({record['id'] for record in PROPERTIES}) == len(PROPERTIES)
    credits = json.loads((BASE / 'static/discovery/photo-credits.json').read_text())
    assert len(credits) == 3
    assert all(row['source'].startswith('https://unsplash.com/photos/') for row in credits)
