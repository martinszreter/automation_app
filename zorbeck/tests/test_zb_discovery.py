"""User-facing discovery and registration; no real registration or email in tests."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit
from html.parser import HTMLParser

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from zorbeck_app.config import settings
from zorbeck_app.discovery import PROPERTIES, attempts, discovery_context
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
    if outcome == 'success':
        target = urlsplit(response.json()['next_url'])
        assert target.path == '/search'
        assert parse_qs(target.query) == {'location': ['Lisbon'], 'budget': ['600000']}
        assert VALID['email'] not in response.json()['next_url']
    else:
        assert 'next_url' not in response.json()


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


@pytest.mark.asyncio
async def test_property_interest_continues_to_selected_example_after_sink_success(monkeypatch):
    monkeypatch.setattr(settings, 'signup_webhook_url', 'https://sink.invalid/register')
    receipt = httpx.Response(200, json={'ok': True}, request=httpx.Request('POST', 'https://sink.invalid/register'))
    sink = AsyncMock(return_value=receipt)
    with patch('httpx.AsyncClient.post', sink):
        async with client() as c:
            response = await c.request('POST', '/api/early-access', json={
                **VALID, 'property_id': 'marbella-01', 'next_url': 'https://external.invalid/steal',
            })
    assert response.status_code == 201
    assert response.json()['next_url'] == '/properties/marbella-01'
    payload = sink.await_args.kwargs['json']
    assert payload['property_id'] == 'marbella-01'
    assert payload['property_kind'] == 'illustrative'
    assert payload['property_path'] == '/properties/marbella-01'
    assert 'next_url' not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize('property_id', ['missing', '../search', 'https://external.invalid', None, [], 12])
async def test_invalid_property_interest_never_reaches_sink(property_id, monkeypatch):
    monkeypatch.setattr(settings, 'signup_webhook_url', 'https://sink.invalid/register')
    sink = AsyncMock()
    with patch('httpx.AsyncClient.post', sink):
        async with client() as c:
            response = await c.request('POST', '/api/early-access', json={**VALID, 'property_id': property_id})
    assert response.status_code == 400
    assert 'next_url' not in response.json()
    sink.assert_not_awaited()


class PageElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.asyncio
@pytest.mark.parametrize('record', PROPERTIES, ids=lambda record: record['id'])
async def test_property_pages_have_real_routes_and_honest_example_details(record):
    path = f"/properties/{record['id']}"
    async with client() as c:
        page = await c.get(path)
        head = await c.head(path)
    assert page.status_code == head.status_code == 200
    assert record['title'] in page.text
    assert f"€{record['price']:,}" in page.text
    assert 'Not an active listing' in page.text
    assert 'Not evaluated' in page.text
    assert 'https://unsplash.com/photos/' in page.text
    tags = PageElements(page.text).tags
    scripts = [attrs['src'] for tag, attrs in tags if tag == 'script' and 'src' in attrs]
    assert scripts[0].startswith('/static/registration.js?')
    assert scripts[1].startswith('/static/property.js?')
    ids = [attrs['id'] for _, attrs in tags if 'id' in attrs]
    assert len(ids) == len(set(ids))
    form = next(attrs for tag, attrs in tags if tag == 'form' and attrs.get('id') == 'register-form')
    assert form['method'] == 'post'
    assert form['action'] == '/api/early-access'


@pytest.mark.asyncio
async def test_unknown_property_is_not_substituted_with_an_offer():
    async with client() as c:
        response = await c.get('/properties/not-a-property')
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('location,budget,expected', [
    ('  LÍSBON portugal ', '400000', ['lisbon-01']),
    ('Spain', '600000', ['marbella-01', 'barcelona-01']),
    ('Lisbon', '300000', []),
    ('Tokyo', '', []),
])
async def test_search_page_preserves_filters_and_renders_matching_examples(location, budget, expected):
    async with client() as c:
        page = await c.get('/search', params={'location': location, 'budget': budget})
    assert page.status_code == 200
    tags = PageElements(page.text).tags
    visible = [attrs['data-property'] for _, attrs in tags if 'data-property' in attrs and 'hidden' not in attrs]
    assert visible == expected
    search_input = next(attrs for _, attrs in tags if attrs.get('id') == 'search-input')
    assert search_input['value'] == ' '.join(location.split())
    selected = [attrs['value'] for tag, attrs in tags if tag == 'option' and 'selected' in attrs]
    assert selected == ([budget] if budget else [])
    empty = next(attrs for _, attrs in tags if attrs.get('id') == 'empty-state')
    assert ('hidden' in empty) is bool(expected)


@pytest.mark.asyncio
async def test_search_escapes_user_input_and_bounds_invalid_budgets():
    injection = '\"><script>alert(1)</script>'
    async with client() as c:
        page = await c.get('/search', params={'location': injection, 'budget': '9' * 200})
    assert page.status_code == 200
    assert '<script>alert(1)</script>' not in page.text
    assert discovery_context('a' * 200, '9' * 200)['initial_filters'] == {'query': 'a' * 80, 'budget': 0}
    for budget in ['-1', '1e6', '²', '1000000001']:
        assert discovery_context('', budget)['initial_filters']['budget'] == 0
