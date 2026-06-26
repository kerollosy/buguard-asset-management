from datetime import date, timedelta

import pytest
from httpx import AsyncClient


def payload(**overrides):
    return {
        "type": "domain",
        "value": "example.com",
        "status": "active",
        "source": "manual",
        "tags": ["root"],
        "metadata": {},
        **overrides,
    }

@pytest.mark.asyncio
async def test_create_asset(async_client: AsyncClient):
    r = await async_client.post("/api/v1/assets/", json=payload())
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "domain"
    assert body["value"] == "example.com"
    assert body["status"] == "active"
    assert "id" in body
    assert "first_seen" in body
    assert "last_seen" in body


@pytest.mark.asyncio
async def test_duplicate_create_asset(async_client: AsyncClient):
    await async_client.post("/api/v1/assets/", json=payload())
    r = await async_client.post("/api/v1/assets/", json=payload())
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_asset(async_client: AsyncClient):
    created = (await async_client.post("/api/v1/assets/", json=payload())).json()
    r = await async_client.get(f"/api/v1/assets/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_asset_not_found(async_client: AsyncClient):
    r = await async_client.get("/api/v1/assets/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_asset(async_client: AsyncClient):
    created = (await async_client.post("/api/v1/assets/", json=payload())).json()
    r = await async_client.patch(
        f"/api/v1/assets/{created['id']}",
        json={"status": "stale", "tags": ["prod", "updated"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "stale"
    assert "prod" in body["tags"]


@pytest.mark.asyncio
async def test_delete_asset(async_client: AsyncClient):
    created = (await async_client.post("/api/v1/assets/", json=payload())).json()
    r = await async_client.delete(f"/api/v1/assets/{created['id']}")
    assert r.status_code == 204

    r = await async_client.get(f"/api/v1/assets/{created['id']}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mark_stale(async_client: AsyncClient):
    created = (await async_client.post("/api/v1/assets/", json=payload())).json()
    r = await async_client.post(f"/api/v1/assets/{created['id']}/stale")
    assert r.status_code == 200
    assert r.json()["status"] == "stale"


# Filtering

@pytest.mark.asyncio
async def test_filter_by_type(async_client: AsyncClient):
    await async_client.post("/api/v1/assets/", json=payload(value="filter-domain.com"))
    await async_client.post(
        "/api/v1/assets/",
        json=payload(type="subdomain", value="sub.filter-domain.com"),
    )

    r = await async_client.get("/api/v1/assets/", params={"type": "domain"})
    assert r.status_code == 200
    body = r.json()
    print(body)
    assert all(a["type"] == "domain" for a in body["items"])


@pytest.mark.asyncio
async def test_filter_by_status(async_client: AsyncClient):
    created = (await async_client.post("/api/v1/assets/", json=payload(value="status-test.com"))).json()
    await async_client.post(f"/api/v1/assets/{created['id']}/stale")

    r = await async_client.get("/api/v1/assets/", params={"status": "stale"})
    assert r.status_code == 200
    assert all(a["status"] == "stale" for a in r.json()["items"])


@pytest.mark.asyncio
async def test_filter_by_tag(async_client: AsyncClient):
    await async_client.post("/api/v1/assets/", json=payload(value="tagged.com", tags=["prod", "external"]))
    await async_client.post("/api/v1/assets/", json=payload(value="other.com", tags=["dev"]))

    r = await async_client.get("/api/v1/assets/", params={"tag": "prod"})
    items = r.json()["items"]
    assert len(items) >= 1
    assert all("prod" in a["tags"] for a in items)


@pytest.mark.asyncio
async def test_filter_by_value_contains(async_client: AsyncClient):
    await async_client.post("/api/v1/assets/", json=payload(value="api.example.com"))
    await async_client.post("/api/v1/assets/", json=payload(value="unrelated.org"))

    r = await async_client.get("/api/v1/assets/", params={"value_contains": "api.example"})
    items = r.json()["items"]
    assert len(items) >= 1
    assert all("api.example" in a["value"] for a in items)


# Certificate lifecycle filtering

@pytest.mark.asyncio
async def test_filter_expired_certificates(async_client: AsyncClient):
    await async_client.post(
        "/api/v1/assets/",
        json=payload(
            type="certificate",
            value="CN=expired.example.com",
            metadata={"expires": "2000-01-01"},
        ),
    )
    await async_client.post(
        "/api/v1/assets/",
        json=payload(
            type="certificate",
            value="CN=future.example.com",
            metadata={"expires": "2099-01-01"},
        ),
    )
    await async_client.post(
        "/api/v1/assets/",
        json=payload(type="domain", value="non-cert.example.com"),
    )

    r = await async_client.get(
        "/api/v1/assets/",
        params={"certificate_lifecycle": "expired"},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "certificate"
    assert items[0]["value"] == "CN=expired.example.com"


@pytest.mark.asyncio
async def test_filter_expiring_soon_certificates(async_client: AsyncClient):
    soon = (date.today() + timedelta(days=10)).isoformat()
    later = (date.today() + timedelta(days=90)).isoformat()

    await async_client.post(
        "/api/v1/assets/",
        json=payload(
            type="certificate",
            value="CN=soon.example.com",
            metadata={"expires": soon},
        ),
    )
    await async_client.post(
        "/api/v1/assets/",
        json=payload(
            type="certificate",
            value="CN=later.example.com",
            metadata={"expires": later},
        ),
    )

    r = await async_client.get(
        "/api/v1/assets/",
        params={
            "certificate_lifecycle": "expiring_soon",
            "expiring_within_days": 40,
        },
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["value"] == "CN=soon.example.com"


# Pagination

@pytest.mark.asyncio
async def test_pagination(async_client: AsyncClient):
    for i in range(5):
        await async_client.post("/api/v1/assets/", json=payload(value=f"page{i}.com"))

    r = await async_client.get("/api/v1/assets/", params={"page": 1, "size": 2})
    body = r.json()
    assert body["total"] >= 5
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["size"] == 2


@pytest.mark.asyncio
async def test_max_page_size_enforced(async_client: AsyncClient):
    r = await async_client.get("/api/v1/assets/", params={"size": 9999})
    assert r.status_code == 422


# Tagging

@pytest.mark.asyncio
async def test_add_tags(async_client: AsyncClient):
    created = (await async_client.post("/api/v1/assets/", json=payload(tags=["root"]))).json()
    r = await async_client.post(
        f"/api/v1/assets/{created['id']}/tags",
        json={"tags": ["prod", "external"]},
    )
    assert r.status_code == 200
    tags = r.json()["tags"]
    assert "root" in tags
    assert "prod" in tags
    assert "external" in tags


# Validation

@pytest.mark.asyncio
async def test_invalid_type_rejected(async_client: AsyncClient):
    r = await async_client.post(
        "/api/v1/assets/", json={**payload(), "type": "not_a_real_type"}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_empty_value_rejected(async_client: AsyncClient):
    r = await async_client.post("/api/v1/assets/", json={**payload(), "value": ""})
    assert r.status_code == 422
