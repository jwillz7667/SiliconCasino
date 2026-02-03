from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=20,  # Increased for Phase 3 scale
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections every 30 minutes
    connect_args={
        "server_settings": {
            "statement_timeout": "30000",  # 30 second query timeout
            "idle_in_transaction_session_timeout": "60000",  # 60 second idle timeout
        }
    },
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database connection and create tables if needed."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
