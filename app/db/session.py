from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

from urllib.parse import urlsplit, urlunsplit

_parts = urlsplit(settings.database_url)
_scheme = "postgresql+asyncpg"
_db_url = urlunsplit((_scheme, _parts.netloc, _parts.path, _parts.query, _parts.fragment))

engine = create_async_engine(_db_url, echo=False)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
