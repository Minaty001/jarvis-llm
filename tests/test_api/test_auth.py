"""
Tests for Authentication API Endpoints.
"""

import pytest
from httpx import AsyncClient, ASGITransport

# We'll test the auth endpoints by mocking the database client


@pytest.mark.asyncio
async def test_login_missing_device_id():
    """Login with empty device_id should return 422 validation error."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/auth/login", json={"device_id": ""})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_check():
    """Health endpoint should return 200."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
