import pytest
from httpx import AsyncClient


payload = {
    "type": "domain",
    "value": "example.com",
    "source": "manual",
    "tags": ["test"],
    "metadata": {"test_key": "test_value"}
}

@pytest.mark.asyncio
async def test_create_asset(async_client: AsyncClient):
    r = await async_client.post("/assets/", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "domain"
    assert body["value"] == "example.com"
    assert body["status"] == "active"
    assert "id" in body
    assert "first_seen" in body
    assert "last_seen" in body


@pytest.mark.asyncio
async def test_get_asset(async_client: AsyncClient):
    created = (await async_client.post("/assets/", json=payload)).json()
    r = await async_client.get(f"/assets/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_asset_not_found(async_client: AsyncClient):
    r = await async_client.get("/assets/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_asset(async_client: AsyncClient):
    created = (await async_client.post("/assets/", json=payload)).json()
    r = await async_client.put(
        f"/assets/{created['id']}",
        json={"status": "stale", "tags": ["prod", "updated"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "stale"
    assert "prod" in body["tags"]


@pytest.mark.asyncio
async def test_delete_asset(async_client: AsyncClient):
    created = (await async_client.post("/assets/", json=payload)).json()
    r = await async_client.delete(f"/assets/{created['id']}")
    assert r.status_code == 204

    r = await async_client.get(f"/assets/{created['id']}")
    assert r.status_code == 404
