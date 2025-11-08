"""
Database configuration and session management
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database (create tables, enable extensions)"""
    from app.models import (
        Account, User, Partner, Call, CallMetricsHourly,
        Transcript, Summary, WebhookEvent
    )
    
    async with engine.begin() as conn:
        # Enable TimescaleDB if configured
        if settings.ENABLE_TIMESCALE:
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
            except Exception:
                pass  # TimescaleDB not available
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

