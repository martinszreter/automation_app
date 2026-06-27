#!/usr/bin/env python3
"""Seed realistic demo data for STARTEND (manual script — never runs on app startup).

Inserts one demo tenant ("Restaurant Bergblick"), ~8 guests and ~15 bookings
spread across the next 7 days so they show up on the dashboard (which lists
today + upcoming bookings).

The script is idempotent: every row uses a deterministic UUID (uuid5) derived
from a fixed namespace, so re-running performs an upsert instead of creating
duplicates. Booking times are recomputed relative to "now" on every run.

DATABASE_URL is read exactly the way the app reads it (via app.core.config /
app.db.session, which normalizes `postgres://` and `postgresql://` to
`postgresql+asyncpg://`).

--------------------------------------------------------------------------------
RUN AGAINST THE RAILWAY DATABASE
--------------------------------------------------------------------------------
Use the *public* connection string from the Railway dashboard
(Postgres service -> "Connect" -> "Public Network" -> Postgres Connection URL),
which looks like postgresql://postgres:PASSWORD@HOST.proxy.rlwy.net:PORT/railway

Seed:

    DATABASE_URL="postgresql://postgres:PASSWORD@HOST.proxy.rlwy.net:PORT/railway" \
        python scripts/seed_demo.py

Wipe only this demo data:

    DATABASE_URL="postgresql://postgres:PASSWORD@HOST.proxy.rlwy.net:PORT/railway" \
        python scripts/seed_demo.py --clear

(If you have the Railway CLI linked to the project you can instead run:
    railway run python scripts/seed_demo.py
which injects the service's DATABASE_URL for you.)
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Make the app package importable when running this file directly from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.db.models import Booking, BookingStatus, Guest, Tenant  # noqa: E402
from app.db.session import async_session, engine  # noqa: E402

# Fixed namespace so generated UUIDs are stable across runs (idempotency).
DEMO_NAMESPACE = uuid.UUID("9f2c1a7e-3b4d-5e6f-8a9b-0c1d2e3f4a5b")

TENANT_TZ = "Europe/Zurich"


def _demo_id(kind: str, key: str) -> uuid.UUID:
    """Deterministic UUID for a demo row, e.g. _demo_id("guest", "anna.mueller")."""
    return uuid.uuid5(DEMO_NAMESPACE, f"{kind}:{key}")


# --- Tenant -------------------------------------------------------------------
TENANT = {
    "id": _demo_id("tenant", "restaurant-bergblick"),
    "name": "Restaurant Bergblick",
    "phone_number": "+41445556677",  # Zurich landline
    "timezone": TENANT_TZ,
}

# --- Guests -------------------------------------------------------------------
# (key, name, phone) — Swiss (+41) and German (+49) numbers.
GUESTS = [
    ("anna-mueller", "Anna Müller", "+41791234567"),
    ("luca-bianchi", "Luca Bianchi", "+41782345678"),
    ("sophie-keller", "Sophie Keller", "+41763456789"),
    ("jonas-weber", "Jonas Weber", "+491512345678"),
    ("elena-fischer", "Elena Fischer", "+41794567890"),
    ("marco-brunner", "Marco Brunner", "+41785678901"),
    ("laura-schmid", "Laura Schmid", "+491609876543"),
    ("david-steiner", "David Steiner", "+41766789012"),
]

# --- Bookings -----------------------------------------------------------------
# (booking_key, guest_index, day_offset, hour, minute, party_size, status, notes)
# day_offset is days from today; times mix lunch (~12-13) and dinner (~18-21).
BOOKINGS = [
    ("b01", 0, 0, 12, 0, 2, BookingStatus.CONFIRMED, "Fensterplatz gewünscht"),
    ("b02", 1, 0, 19, 0, 4, BookingStatus.PENDING, None),
    ("b03", 2, 0, 20, 30, 6, BookingStatus.REMINDER_SENT, "Geburtstag"),
    ("b04", 3, 1, 12, 30, 3, BookingStatus.CONFIRMED, None),
    ("b05", 4, 1, 18, 30, 2, BookingStatus.PENDING, "Allergie: Nüsse"),
    ("b06", 5, 1, 20, 0, 8, BookingStatus.CONFIRMED, "Firmenessen"),
    ("b07", 6, 2, 13, 0, 4, BookingStatus.REMINDER_SENT, None),
    ("b08", 7, 2, 19, 30, 2, BookingStatus.CANCELLED, "Gast hat abgesagt"),
    ("b09", 0, 3, 12, 0, 5, BookingStatus.CONFIRMED, None),
    ("b10", 2, 3, 19, 0, 3, BookingStatus.PENDING, "Kinderstuhl benötigt"),
    ("b11", 4, 4, 18, 30, 4, BookingStatus.REMINDER_SENT, None),
    ("b12", 1, 4, 20, 30, 6, BookingStatus.CONFIRMED, "Terrasse"),
    ("b13", 5, 5, 12, 30, 2, BookingStatus.PENDING, None),
    ("b14", 6, 5, 19, 0, 7, BookingStatus.CONFIRMED, "Vegetarisches Menü"),
    ("b15", 3, 6, 20, 0, 4, BookingStatus.REMINDER_SENT, None),
]


def _build_rows() -> tuple[dict, list[dict], list[dict]]:
    tz = ZoneInfo(TENANT_TZ)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    tenant_row = dict(TENANT)

    guest_rows: list[dict] = []
    guest_ids: list[uuid.UUID] = []
    for key, name, phone in GUESTS:
        gid = _demo_id("guest", key)
        guest_ids.append(gid)
        guest_rows.append(
            {"id": gid, "phone_number": phone, "name": name, "language": "de"}
        )

    booking_rows: list[dict] = []
    for bkey, gidx, day, hour, minute, party, status, notes in BOOKINGS:
        booked_at = (today + timedelta(days=day)).replace(hour=hour, minute=minute)
        booking_rows.append(
            {
                "id": _demo_id("booking", bkey),
                "tenant_id": tenant_row["id"],
                "guest_id": guest_ids[gidx],
                "party_size": party,
                "booked_at": booked_at,
                "status": status,
                "notes": notes,
            }
        )

    return tenant_row, guest_rows, booking_rows


async def seed() -> None:
    tenant_row, guest_rows, booking_rows = _build_rows()

    async with async_session() as session:
        # Upsert tenant (conflict on PK -> update mutable fields).
        await session.execute(
            pg_insert(Tenant)
            .values(**tenant_row)
            .on_conflict_do_update(
                index_elements=[Tenant.id],
                set_={
                    "name": tenant_row["name"],
                    "phone_number": tenant_row["phone_number"],
                    "timezone": tenant_row["timezone"],
                },
            )
        )

        for row in guest_rows:
            await session.execute(
                pg_insert(Guest)
                .values(**row)
                .on_conflict_do_update(
                    index_elements=[Guest.id],
                    set_={
                        "phone_number": row["phone_number"],
                        "name": row["name"],
                        "language": row["language"],
                    },
                )
            )

        for row in booking_rows:
            await session.execute(
                pg_insert(Booking)
                .values(**row)
                .on_conflict_do_update(
                    index_elements=[Booking.id],
                    set_={
                        "tenant_id": row["tenant_id"],
                        "guest_id": row["guest_id"],
                        "party_size": row["party_size"],
                        "booked_at": row["booked_at"],
                        "status": row["status"],
                        "notes": row["notes"],
                    },
                )
            )

        await session.commit()

    print(
        f"Seeded demo data: 1 tenant ({tenant_row['name']}), "
        f"{len(guest_rows)} guests, {len(booking_rows)} bookings."
    )


async def clear() -> None:
    tenant_row, guest_rows, booking_rows = _build_rows()
    booking_ids = [r["id"] for r in booking_rows]
    guest_ids = [r["id"] for r in guest_rows]

    async with async_session() as session:
        # Bookings first (FK), then guests, then tenant — all by stable demo IDs only.
        await session.execute(delete(Booking).where(Booking.id.in_(booking_ids)))
        await session.execute(delete(Guest).where(Guest.id.in_(guest_ids)))
        await session.execute(delete(Tenant).where(Tenant.id == tenant_row["id"]))
        await session.commit()

    print(
        f"Cleared demo data: {len(booking_ids)} bookings, "
        f"{len(guest_ids)} guests, 1 tenant."
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed STARTEND demo data.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Wipe only the demo data created by this script.",
    )
    args = parser.parse_args()

    try:
        if args.clear:
            await clear()
        else:
            await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
