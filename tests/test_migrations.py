"""Verify that 'alembic upgrade head' creates all expected tables."""

import asyncio
import os

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:test@localhost:5432/startend_migration_test",
)


async def _run_alembic_upgrade(db_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url.replace("+asyncpg", ""))

    from app.db.session import _force_asyncpg_url
    from alembic import context  # noqa: F811

    async_url = _force_asyncpg_url(db_url)
    engine = create_async_engine(async_url)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: command.upgrade(cfg, "head")
        )
    await engine.dispose()


async def _get_tables(db_url: str) -> set[str]:
    engine = create_async_engine(db_url)
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    await engine.dispose()
    return set(table_names)


async def _setup_and_check() -> set[str]:
    from sqlalchemy.ext.asyncio import create_async_engine as cae

    engine = cae(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()

    os.environ["DATABASE_URL"] = TEST_DB_URL
    from subprocess import run as subprocess_run

    result = subprocess_run(
        ["python", "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": TEST_DB_URL},
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed:\n{result.stderr}")

    return await _get_tables(TEST_DB_URL)


@pytest.mark.asyncio
async def test_migrations_create_all_tables():
    tables = await _setup_and_check()
    assert "tenants" in tables, f"tenants table missing, got: {tables}"
    assert "guests" in tables, f"guests table missing, got: {tables}"
    assert "bookings" in tables, f"bookings table missing, got: {tables}"
