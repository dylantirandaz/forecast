"""API tests for the /api/v1/questions endpoints.

Uses httpx AsyncClient with an in-memory SQLite database via the
conftest.py fixtures.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_question_payload(**overrides) -> dict:
    """Return a valid QuestionCreate payload with optional overrides."""
    payload = {
        "title": "Will the NYC vacancy rate for stabilised apartments drop below 1.5% by 2028?",
        "description": (
            "Tracks the rental vacancy rate for rent-stabilised units "
            "across all five boroughs."
        ),
        "target_type": "binary",
        "resolution_criteria": (
            "Resolves YES if the NYCHVS reports a vacancy rate below 1.5% "
            "for rent-stabilised units in the 2028 survey."
        ),
        "resolution_date": "2029-01-01T00:00:00+00:00",
        "tags": ["housing", "vacancy"],
    }
    payload.update(overrides)
    return payload


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestCreateQuestion:
    """POST /api/v1/questions"""

    async def test_create_question(self, client: AsyncClient):
        """Creating a question should return 201 with the new resource."""
        payload = _make_question_payload()
        resp = await client.post("/api/v1/questions", json=payload)

        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == payload["title"]
        assert data["target_type"] == "binary"
        assert "id" in data

    async def test_create_question_validation_error(self, client: AsyncClient):
        """A title that is too short should be rejected with 422."""
        payload = _make_question_payload(title="Short")
        resp = await client.post("/api/v1/questions", json=payload)
        assert resp.status_code == 422


class TestListQuestions:
    """GET /api/v1/questions"""

    async def test_list_questions(self, client: AsyncClient):
        """Listing questions should return a paginated response."""
        # Create two questions first.
        await client.post(
            "/api/v1/questions",
            json=_make_question_payload(title="Question one -- will median rent exceed $1700 by 2029?"),
        )
        await client.post(
            "/api/v1/questions",
            json=_make_question_payload(title="Question two -- will vacancy rate fall below 2% by 2028?"),
        )

        resp = await client.get("/api/v1/questions")
        assert resp.status_code == 200

        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2
        assert len(data["items"]) >= 2


class TestGetQuestion:
    """GET /api/v1/questions/{id}"""

    async def test_get_question(self, client: AsyncClient):
        """Fetching a question by ID should return its full representation."""
        create_resp = await client.post(
            "/api/v1/questions",
            json=_make_question_payload(),
        )
        question_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/questions/{question_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == question_id

    async def test_get_question_not_found(self, client: AsyncClient):
        """A non-existent question ID should return 404."""
        resp = await client.get(
            "/api/v1/questions/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


class TestUpdateQuestion:
    """PUT /api/v1/questions/{id}"""

    async def test_update_question(self, client: AsyncClient):
        """Updating a question should modify the specified fields."""
        create_resp = await client.post(
            "/api/v1/questions",
            json=_make_question_payload(),
        )
        question_id = create_resp.json()["id"]

        update_payload = {
            "title": "Updated title: will the stabilised vacancy rate exceed 3% by 2029?",
        }
        resp = await client.put(
            f"/api/v1/questions/{question_id}",
            json=update_payload,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == update_payload["title"]

    async def test_update_question_not_found(self, client: AsyncClient):
        """Updating a non-existent question should return 404."""
        resp = await client.put(
            "/api/v1/questions/00000000-0000-0000-0000-000000000000",
            json={"title": "This question does not exist in the database at all"},
        )
        assert resp.status_code == 404
