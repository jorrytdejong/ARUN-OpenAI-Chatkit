"""Database engine and URL helpers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


def _normalize_base_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def to_async_database_url(url: str) -> str:
    normalized = _normalize_base_database_url(url)
    if normalized.startswith("postgresql+psycopg://"):
        return normalized.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
    if normalized.startswith("sqlite+aiosqlite://"):
        return normalized
    if normalized.startswith("sqlite://"):
        return normalized.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return normalized


def to_sync_database_url(url: str) -> str:
    normalized = _normalize_base_database_url(url)
    if normalized.startswith("postgresql+asyncpg://"):
        return normalized.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    if normalized.startswith("sqlite+aiosqlite://"):
        return normalized.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return normalized


class Base(DeclarativeBase):
    pass


def create_engine_and_session_factory(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker]:
    engine = create_async_engine(
        to_async_database_url(database_url),
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory
