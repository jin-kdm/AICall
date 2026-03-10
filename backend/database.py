import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def _migrate_timestamps_pg(conn):
    """Migrate TIMESTAMP WITHOUT TIME ZONE columns to WITH TIME ZONE on PostgreSQL."""
    migrations = [
        "ALTER TABLE scenarios ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE scenarios ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE audio_cache ALTER COLUMN generated_at TYPE TIMESTAMP WITH TIME ZONE",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
        except Exception:
            pass  # Column already correct or table doesn't exist yet


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate existing PostgreSQL columns if needed
        if "postgresql" in settings.database_url:
            await _migrate_timestamps_pg(conn)
