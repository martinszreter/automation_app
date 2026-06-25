from urllib.parse import urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _force_asyncpg_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in ("postgres", "postgresql", "postgresql+psycopg2"):
        parsed = parsed._replace(scheme="postgresql+asyncpg")
    return urlunparse(parsed)


_db_url = _force_asyncpg_url(settings.database_url)
print(f"[STARTEND] engine URL scheme: {_db_url.split('://')[0]}")

engine = create_async_engine(_db_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
