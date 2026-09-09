"""Verify that 'alembic upgrade head' creates all expected tables.

Needs a real Postgres (``TEST_DATABASE_URL``); the test skips itself when none
is listening so the rest of the suite stays runnable on a laptop without one.
CI provides the database, so the skip never hides a broken migration there.
"""

import os
from subprocess import run as subprocess_run

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:test@localhost:5432/startend_migration_test",
)

EXPECTED_TABLES = {"tenants", "guests", "bookings", "contact_requests", "x_autopilot_plans"}


async def _reset_schema() -> None:
    engine = create_async_engine(TEST_DB_URL)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    except OSError as exc:
        pytest.skip(f"no test database at {TEST_DB_URL}: {exc}")
    finally:
        await engine.dispose()


async def _get_tables() -> set[str]:
    engine = create_async_engine(TEST_DB_URL)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names()))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migrations_create_all_tables() -> None:
    await _reset_schema()

    result = subprocess_run(
        ["python", "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": TEST_DB_URL},
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stderr}"

    tables = await _get_tables()
    missing = EXPECTED_TABLES - tables
    assert not missing, f"tables missing after upgrade: {sorted(missing)}; got {sorted(tables)}"
