"""Original factual source summaries and approved first-party advertisements."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

from zorbeck_app.market_store import available, database

BASE = Path(__file__).resolve().parent.parent
SOURCED = json.loads((BASE / "data/sourced-properties.json").read_text())
# Snapshot, not a live conversion service. Always expose its date next to estimates.
FX_DATE = "2026-09-11"
FX_SOURCE = "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html"
FX = {"EUR": 1.0, "JPY": 178.56, "USD": 1.1592, "CHF": 0.9451,
      "GBP": 0.85815, "CNY": 7.7762, "THB": 38.329, "AUD": 1.6161,
      "CAD": 1.6064, "SGD": 1.4697, "IDR": 20404.99, "PLN": 4.3250}
COUNTRY_NAMES = {"United States of America": "United States", "Republic of Serbia": "Serbia",
                 "United Republic of Tanzania": "Tanzania", "eSwatini": "Eswatini"}
COUNTRIES = sorted({COUNTRY_NAMES.get(feature["properties"]["country"], feature["properties"]["country"]) for feature in json.loads(
    (BASE / "static/discovery/world-countries.json").read_text())["features"]}
    | {"United States", "United Kingdom", "Singapore", "Malta", "Bahrain", "Maldives",
       "Andorra", "Antigua and Barbuda", "Barbados", "Cabo Verde", "Comoros", "Dominica",
       "Grenada", "Kiribati", "Liechtenstein", "Marshall Islands", "Mauritius", "Micronesia",
       "Monaco", "Nauru", "Palau", "Saint Kitts and Nevis", "Saint Lucia",
       "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe",
       "Seychelles", "Tonga", "Tuvalu", "Vatican City"})


def decorate(item: dict) -> dict:
    p = dict(item)
    amount, currency = p["asking_price"], p["currency"]
    p["price"] = round(amount / FX[currency], 2) if currency in FX else None
    prefix = {"EUR": "€", "JPY": "¥", "USD": "$", "GBP": "£"}.get(currency, currency+" ")
    p["price_label"] = prefix + f"{amount:,.0f}" if amount == int(amount) else prefix + f"{amount:,.2f}"
    p["eur_label"] = "€"+f"{p['price']:,.0f}" if p["price"] is not None else "EUR comparison unavailable"
    p["fx_date"] = FX_DATE
    p["image_url"] = "/media/"+p["photos"][0] if p.get("photos") else ""
    p["imageAlt"] = "Seller-supplied photograph of "+p["title"] if p["image_url"] else ""
    p["featured"] = bool(p.get("promotion_until", 0) > time.time())
    p["status_label"] = "Featured · paid placement" if p["featured"] else "Seller listing" if p["kind"] == "seller" else "Source advertisement"
    p["availability"] = "Seller reports available" if p["kind"] == "seller" else "Confirm with original advertiser"
    p["coordinates_note"] = "Approximate area; not the property's exact address"
    checked = date.fromisoformat(p["source_checked"])
    p["needs_recheck"] = (date.today()-checked).days > 30
    return p


def public_properties() -> list[dict]:
    now = int(time.time())
    rows = []
    overrides = {}
    if available():
        with database() as conn:
            overrides = {r["key"][7:]: json.loads(r["value"]) for r in conn.execute(
                "SELECT key,value FROM app_meta WHERE key LIKE 'source:%'")}
            rows = conn.execute(
                "SELECT l.*, COALESCE((SELECT MAX(o.promotion_until) FROM orders o "
                "WHERE o.listing_id=l.id AND o.status='paid'),0) AS promotion_until "
                "FROM listings l WHERE l.status='published' AND l.updated_at>? "
                "ORDER BY promotion_until DESC,l.published_at DESC LIMIT 500", (now-90*86400,)).fetchall()
    output = []
    for row in rows:
        item = json.loads(row["data_json"])
        for private_field in ("authority", "photo_rights", "distribution_consent", "reference_url"):
            item.pop(private_field, None)
        item.update(id=row["id"], kind="seller", source_name="Direct seller submission",
                    source_url="", source_checked=datetime.fromtimestamp(row["updated_at"], timezone.utc).date().isoformat(),
                    source_updated=None, promotion_until=row["promotion_until"],
                    considerations=["Details and photos supplied by the seller.",
                                    "Check title, authority to sell, condition and purchase costs with your own professional."])
        output.append(decorate(item))
    for item in SOURCED:
        override = overrides.get(item["id"], {})
        if not override.get("hidden"):
            output.append(decorate({**item, "source_checked": override.get("checked", item["source_checked"])}))
    return sorted(output, key=lambda p: not p["featured"])


def find_public(property_id: str):
    return next((p for p in public_properties() if p["id"] == property_id), None)
