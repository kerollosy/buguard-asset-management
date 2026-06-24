import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """Test that valid credentials return a JWT token."""
    # Note: OAuth2 strictly requires 'data' (Form encoded) instead of 'json'
    response = await async_client.post(
        "/auth/token",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
        },
    )
    
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure(async_client: AsyncClient):
    """Test that invalid credentials are rejected."""
    response = await async_client.post(
        "/auth/token",
        data={
            "username": settings.ADMIN_USERNAME,
            "password": "wrong_password",
        },
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"


@pytest.mark.parametrize(
    "method, path",
    [
        ("POST", "/assets/"),
        ("PATCH", "/assets/00000000-0000-0000-0000-000000000000"),
        ("DELETE", "/assets/00000000-0000-0000-0000-000000000000"),
        ("POST", "/assets/00000000-0000-0000-0000-000000000000/tags"),
        ("POST", "/assets/bulk"),
        ("POST", "/assets/relationships"),
        ("DELETE", "/assets/relationships/00000000-0000-0000-0000-000000000000"),
    ],
)
@pytest.mark.asyncio
async def test_write_routes_require_auth(unauthed_client: AsyncClient, method: str, path: str):
    """
    Ensures that ALL write/mutation endpoints reject unauthenticated requests.
    We don't care about the body payload here, because the auth dependency
    runs before body validation. It should immediately return a 401.
    """
    response = await unauthed_client.request(method, path)
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_read_routes_allow_unauthed(unauthed_client: AsyncClient):
    """Ensure that GET endpoints are still public."""
    response = await unauthed_client.get("/assets/")
    
    assert response.status_code != 401
