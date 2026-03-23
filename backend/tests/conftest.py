"""Shared pytest fixtures for the NYC Housing Forecasting test suite.

Uses an in-memory SQLite database with aiosqlite for fast isolated tests.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import get_db
from app.models.base import Base


# ---------------------------------------------------------------------------
# Async SQLite engine for testing
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def async_engine():
    """Create an async SQLite engine scoped to the test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # SQLite needs foreign-key enforcement turned on explicitly.
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional async session that rolls back after each test."""
    session_factory = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Test HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx AsyncClient wired to the FastAPI app with the test DB."""
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def sample_question(db_session: AsyncSession):
    """Insert and return a sample ForecastingQuestion."""
    from app.models.question import ForecastingQuestion, QuestionStatus, TargetType

    q = ForecastingQuestion(
        id=uuid.uuid4(),
        title="Will median stabilised rent in NYC exceed $1,600/month by 2027?",
        description=(
            "Tracks the median legal regulated rent for rent-stabilised "
            "apartments across all five boroughs of New York City."
        ),
        target_type=TargetType.binary,
        target_metric="median_rent_stabilised",
        unit_of_analysis="nyc",
        forecast_horizon_months=24,
        resolution_criteria=(
            "Resolves YES if the NYCHVS or RGB survey reports a median "
            "stabilised rent at or above $1,600/month for calendar year 2027."
        ),
        status=QuestionStatus.active,
        resolution_date=date(2028, 3, 1),
    )
    db_session.add(q)
    await db_session.flush()
    await db_session.refresh(q)
    return q


@pytest_asyncio.fixture()
async def sample_scenario(db_session: AsyncSession):
    """Insert and return a sample Scenario."""
    from app.models.scenario import Scenario, ScenarioIntensity

    s = Scenario(
        id=uuid.uuid4(),
        name="Full Rent Freeze",
        narrative=(
            "The RGB adopts a 0% guideline increase for four consecutive "
            "years, with no offsetting supply-side measures."
        ),
        assumptions={"rgb_increase_1yr_pct": 0.0, "rgb_increase_2yr_pct": 0.5},
        policy_levers={
            "rgb_increase_1yr_pct": 0.0,
            "affordable_construction_boost_pct": 0.0,
        },
        intensity=ScenarioIntensity.aggressive,
    )
    db_session.add(s)
    await db_session.flush()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture()
async def sample_evidence(db_session: AsyncSession):
    """Insert and return a sample EvidenceItem."""
    from app.models.evidence import EvidenceItem, SourceType

    e = EvidenceItem(
        id=uuid.uuid4(),
        title="2025 NYCHVS Preliminary Results",
        source_url="https://www.census.gov/programs-surveys/nychvs.html",
        source_name="US Census Bureau",
        source_type=SourceType.official_data,
        content_summary=(
            "Median gross rent for stabilised apartments rose to $1,525/month "
            "in 2025, a 3.2% year-over-year increase. Vacancy rate for "
            "stabilised units remained below 2%."
        ),
        published_date=date(2025, 12, 15),
    )
    db_session.add(e)
    await db_session.flush()
    await db_session.refresh(e)
    return e
