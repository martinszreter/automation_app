"""Illustrative discovery catalog and acknowledged early-access registration."""

from __future__ import annotations

import time
import unicodedata
from collections import deque
from hashlib import sha256
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from zorbeck_app.config import settings
from zorbeck_app.intake import IntakeError, parse_intake

router = APIRouter()
attempts: dict[str, deque[float]] = {}

# City-level coordinates and fictional examples, never active property listings.
PROPERTIES = [
    {"id": "lisbon-01", "city": "Lisbon", "country": "Portugal", "region": "Europe", "lat": 38.7223, "lng": -9.1393, "title": "A little more room for possibility", "neighborhood": "Lisbon city example", "type": "Apartment", "price": 385000, "beds": 2, "area": 94, "image": "city-apartment.webp", "imageAlt": "Illustrative contemporary apartment building", "tag": "City living", "description": "An illustrative two-bedroom apartment brief for exploring a European city. Compare the asking price, ongoing costs and local rental rules when live listings become available."},
    {"id": "marbella-01", "city": "Marbella", "country": "Spain", "region": "Europe", "lat": 36.5101, "lng": -4.8824, "title": "Space, sunshine, a different pace", "neighborhood": "Costa del Sol example", "type": "Villa", "price": 595000, "beds": 3, "area": 168, "image": "modern-villa.webp", "imageAlt": "Illustrative modern white villa with a pool", "tag": "By the coast", "description": "A sample coastal villa brief with outdoor space. The photo illustrates an architectural style and is not a listing in Marbella. Rental permissions and running costs need to be checked property by property."},
    {"id": "zug-01", "city": "Zug", "country": "Switzerland", "region": "Europe", "lat": 47.1662, "lng": 8.5155, "title": "A fresh perspective on alpine living", "neighborhood": "Zug region example", "type": "House", "price": 1250000, "beds": 3, "area": 142, "image": "alpine-home.webp", "imageAlt": "Illustrative alpine home in a mountain landscape", "tag": "Close to nature", "description": "A fictional family-home brief near the Swiss lakes. The example helps you explore location and space; it is not a valuation, available property, or eligibility assessment."},
    {"id": "london-01", "city": "London", "country": "United Kingdom", "region": "Europe", "lat": 51.5074, "lng": -0.1278, "title": "Your own corner of the city", "neighborhood": "Greater London example", "type": "Apartment", "price": 720000, "beds": 2, "area": 86, "image": "city-apartment.webp", "imageAlt": "Illustrative modern city apartment facade", "tag": "City living", "description": "A sample city apartment to compare with other markets. Prices use illustrative EUR amounts throughout this preview, not current currency conversions or market estimates."},
    {"id": "dubai-01", "city": "Dubai", "country": "United Arab Emirates", "region": "Middle East", "lat": 25.2048, "lng": 55.2708, "title": "Room to think bigger", "neighborhood": "Dubai city example", "type": "Apartment", "price": 465000, "beds": 2, "area": 112, "image": "city-apartment.webp", "imageAlt": "Illustrative contemporary apartment architecture", "tag": "Urban outlook", "description": "An illustrative apartment brief for exploring Dubai. Service charges, ownership rules and rental data would form part of a sourced comparison before any investment decision."},
    {"id": "miami-01", "city": "Miami", "country": "United States", "region": "Americas", "lat": 25.7617, "lng": -80.1918, "title": "A place in the sun", "neighborhood": "Miami area example", "type": "Villa", "price": 895000, "beds": 3, "area": 185, "image": "modern-villa.webp", "imageAlt": "Illustrative contemporary poolside home", "tag": "By the coast", "description": "A fictional warm-weather villa brief. This preview does not estimate returns. Insurance, local taxes and property condition would need current, property-specific evidence."},
    {"id": "bali-01", "city": "Bali", "country": "Indonesia", "region": "Asia Pacific", "lat": -8.4095, "lng": 115.1889, "title": "An outlook beyond the everyday", "neighborhood": "Bali island example", "type": "Villa", "price": 295000, "beds": 2, "area": 125, "image": "modern-villa.webp", "imageAlt": "Illustrative villa architecture with a pool", "tag": "Island living", "description": "A sample island-property brief, not a property offer. Tenure, ownership eligibility and operating permissions must be independently verified for any actual listing."},
    {"id": "barcelona-01", "city": "Barcelona", "country": "Spain", "region": "Europe", "lat": 41.3874, "lng": 2.1686, "title": "City energy. A place to call yours.", "neighborhood": "Barcelona city example", "type": "Apartment", "price": 425000, "beds": 2, "area": 88, "image": "city-apartment.webp", "imageAlt": "Illustrative bright apartment building exterior", "tag": "City living", "description": "An example apartment brief for comparing European city locations. Building condition, fees and permitted use require verification against a real property and current sources."},
]

PROPERTY_BY_ID = {property["id"]: property for property in PROPERTIES}


def normalized(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(char))


def discovery_context(location: str = "", budget: str = "") -> dict:
    """Render the same bounded sample search on the server and in the browser."""
    query = " ".join(location.split())[:80]
    ceiling = int(budget) if budget.isascii() and budget.isdigit() and len(budget) <= 10 else 0
    ceiling = ceiling if 0 < ceiling <= 1_000_000_000 else 0
    words = normalized(query).split()
    matches = [
        property for property in PROPERTIES
        if (not ceiling or property["price"] <= ceiling)
        and all(word in normalized(" ".join(str(property[key]) for key in ("city", "country", "type", "region", "tag"))) for word in words)
    ]
    return {
        "properties": PROPERTIES,
        "initial_filters": {"query": query, "budget": ceiling},
        "matching_ids": [property["id"] for property in matches],
        "result_count": len(matches),
    }


def registration_destination(property_id: str, city: str, budget: int | None) -> str:
    if property_id:
        return f"/properties/{property_id}"
    params = {"location": city}
    if budget:
        params["budget"] = str(budget)
    return "/search?" + urlencode(params)


@router.post("/api/early-access")
async def early_access(request: Request) -> JSONResponse:
    if "application/json" not in request.headers.get("content-type", ""):
        return JSONResponse({"ok": False, "error": "Please submit the registration form."}, status_code=415)
    raw = await request.body()
    if len(raw) > 4096:
        return JSONResponse({"ok": False, "error": "Please keep your request short."}, status_code=413)
    try:
        data = await request.json()
    except ValueError:
        return JSONResponse({"ok": False, "error": "Please check the form and try again."}, status_code=400)
    if not isinstance(data, dict) or data.get("consent") is not True:
        return JSONResponse({"ok": False, "error": "Please accept the privacy notice to register."}, status_code=400)
    if data.get("website"):
        return JSONResponse({"ok": False, "error": "This request could not be accepted."}, status_code=400)
    if len(str(data.get("city", ""))) > 80:
        return JSONResponse({"ok": False, "error": "Please use a shorter location."}, status_code=400)
    try:
        intake = parse_intake(data)
    except IntakeError:
        return JSONResponse({"ok": False, "error": "Enter a valid email, location and budget."}, status_code=400)
    property_id = data.get("property_id", "")
    if not isinstance(property_id, str) or (property_id and property_id not in PROPERTY_BY_ID):
        return JSONResponse({"ok": False, "error": "Choose a property from the preview and try again."}, status_code=400)
    if not settings.signup_webhook_url:
        return JSONResponse({"ok": False, "error": "Registration is temporarily unavailable. Please try again later."}, status_code=503)

    now = time.monotonic()
    address = sha256(intake.email.encode("utf-8")).hexdigest()
    if len(attempts) > 2000:
        for key in list(attempts):
            if not attempts[key] or now - attempts[key][-1] > 60:
                del attempts[key]
    history = attempts.setdefault(address, deque(maxlen=6))
    while history and now - history[0] > 60:
        history.popleft()
    if len(history) >= 5:
        return JSONResponse({"ok": False, "error": "Please wait a minute before trying again."}, status_code=429)
    history.append(now)

    payload = intake.as_row(
        status="early_access", source="zorbeck-explorer", currency="EUR",
        consent_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    if property_id:
        payload.update(property_id=property_id, property_kind="illustrative", property_path=f"/properties/{property_id}")
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(settings.signup_webhook_url, json=payload)
            response.raise_for_status()
            try:
                receipt = response.json()
            except ValueError:
                receipt = None
            if isinstance(receipt, dict) and receipt.get("ok") is False:
                raise ValueError("Registration rejected")
    except (httpx.HTTPError, ValueError):
        return JSONResponse({"ok": False, "error": "We could not save your registration. Please try again."}, status_code=502)
    return JSONResponse({
        "ok": True,
        "message": "You’re on the early-access list. Your search has been saved.",
        "next_url": registration_destination(property_id, intake.city, intake.budget_max),
    }, status_code=201)
