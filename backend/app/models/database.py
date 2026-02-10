"""SQLAlchemy models and database setup."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON, func
from datetime import datetime
from typing import Optional, List
import uuid

from app.core.config import settings


# ─── Engine & Session ───

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine_kwargs: dict = {
    "echo": settings.DEBUG,
}
if not _is_sqlite:
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ─── Models ───

class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="chatting")
    profile_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    symptoms_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    question_count: Mapped[int] = mapped_column(default=0)

    messages: Mapped[List["MessageModel"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    result: Mapped[Optional["ResultModel"]] = relationship(back_populates="session", uselist=False, cascade="all, delete-orphan")


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    role: Mapped[str] = mapped_column(String(10))  # user, ai, system
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["SessionModel"] = relationship(back_populates="messages")


class ResultModel(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), unique=True)
    candidates_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    routing_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10), default="LOW")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["SessionModel"] = relationship(back_populates="result")


# ─── DB Lifecycle ───

async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI routes."""
    async with async_session() as session:
        yield session
