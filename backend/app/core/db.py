from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import func
from datetime import datetime
from config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,          # number of persistent connections kept open
    max_overflow=20,       # extra connections allowed beyond pool_size under load
    pool_timeout=30,       # seconds to wait for a connection before erroring
    pool_recycle=1800,     # recycle connections every 30 min (avoids stale/dead conns)
    pool_pre_ping=True,    # checks connection is alive before using it
    echo=False,            # set True to log SQL (debugging only)
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
class Base(DeclarativeBase, TimestampMixin):
    pass

