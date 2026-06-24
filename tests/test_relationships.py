import pytest
from httpx import AsyncClient


async def _create_asset(client: AsyncClient, type_: str, value: str) -> dict:
    r = await client.post(
        "/api/v1/assets/",
        json={
            "type": type_,
            "value": value,
            "status": "active",
            "source": "manual",
            "tags": [],
            "metadata": {},
        },
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.asyncio
async def test_create_relationship(async_client: AsyncClient):    
    domain = await _create_asset(async_client, "domain", "rel-test.com")
    sub = await _create_asset(async_client, "subdomain", "api.rel-test.com")

    r = await async_client.post(
        "/api/v1/assets/relationships", 
        json={
            "source_id": sub["id"],
            "target_id": domain["id"],
            "relationship_type": "subdomain_of"
        }
    )
    assert r.status_code == 201
    body = r.json()
    assert body["source_id"] == sub["id"]
    assert body["target_id"] == domain["id"]
    assert body["relationship_type"] == "subdomain_of"


@pytest.mark.asyncio
async def test_duplicate_relationship_rejected(async_client: AsyncClient):
    domain = await _create_asset(async_client, "domain", "dup-rel.com")
    sub = await _create_asset(async_client, "subdomain", "api.dup-rel.com")

    payload = {
        "source_id": sub["id"],
        "target_id": domain["id"],
        "relationship_type": "subdomain_of",
    }
    r1 = await async_client.post("/api/v1/assets/relationships", json=payload)
    assert r1.status_code == 201

    r2 = await async_client.post("/api/v1/assets/relationships", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_self_relationship_rejected(async_client: AsyncClient):
    asset = await _create_asset(async_client, "domain", "self-rel.com")
    r = await async_client.post(
        "/api/v1/assets/relationships",
        json={
            "source_id": asset["id"],
            "target_id": asset["id"],
            "relationship_type": "related_to",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_relationship_to_nonexistent_asset_rejected(async_client: AsyncClient):
    asset = await _create_asset(async_client, "domain", "orphan-rel.com")
    r = await async_client.post(
        "/api/v1/assets/relationships",
        json={
            "source_id": asset["id"],
            "target_id": "00000000-0000-0000-0000-000000000000",
            "relationship_type": "related_to",
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_relationships_by_source(async_client: AsyncClient):
    domain = await _create_asset(async_client, "domain", "list-rel.com")
    sub1 = await _create_asset(async_client, "subdomain", "api.list-rel.com")
    sub2 = await _create_asset(async_client, "subdomain", "www.list-rel.com")

    for sub in (sub1, sub2):
        await async_client.post(
            "/api/v1/assets/relationships",
            json={"source_id": sub["id"], "target_id": domain["id"], "relationship_type": "subdomain_of"},
        )

    r = await async_client.get(f"/api/v1/assets/{domain['id']}/graph")
    assert r.status_code == 200
    graph_data = r.json()
    assert len(graph_data["incoming"]) == 2


@pytest.mark.asyncio
async def test_delete_relationship(async_client: AsyncClient):
    domain = await _create_asset(async_client, "domain", "del-rel.com")
    sub = await _create_asset(async_client, "subdomain", "api.del-rel.com")

    created = (
        await async_client.post(
            "/api/v1/assets/relationships",
            json={"source_id": sub["id"], "target_id": domain["id"], "relationship_type": "subdomain_of"},
        )
    ).json()

    print(f"Created relationship: {created}")
    r = await async_client.delete(f"/api/v1/assets/relationships/{created['id']}")
    assert r.status_code == 204

    r = await async_client.get("/api/v1/assets/relationships", params={"source_id": sub["id"]})
    assert r.json() == []


@pytest.mark.asyncio
async def test_asset_graph_endpoint(async_client: AsyncClient):
    domain = await _create_asset(async_client, "domain", "graph.com")
    sub = await _create_asset(async_client, "subdomain", "api.graph.com")

    await async_client.post(
        "/api/v1/assets/relationships",
        json={"source_id": sub["id"], "target_id": domain["id"], "relationship_type": "subdomain_of"},
    )

    r = await async_client.get(f"/api/v1/assets/{sub['id']}/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == sub["id"]
    assert len(body["outgoing"]) == 1
    assert body["outgoing"][0]["relationship_type"] == "subdomain_of"
    assert body["incoming"] == []


@pytest.mark.asyncio
async def test_deleting_asset_cascades_relationships(async_client: AsyncClient):
    """Deleting an asset must also remove its relationship edges."""
    domain = await _create_asset(async_client, "domain", "cascade.com")
    sub = await _create_asset(async_client, "subdomain", "api.cascade.com")

    await async_client.post(
        "/api/v1/assets/relationships",
        json={"source_id": sub["id"], "target_id": domain["id"], "relationship_type": "subdomain_of"},
    )

    await async_client.delete(f"/api/v1/assets/{sub['id']}")

    # The relationship should no longer exist
    r = await async_client.get("/api/v1/assets/relationships", params={"source_id": sub["id"]})
    assert r.json() == []
