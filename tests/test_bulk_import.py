import pytest
from httpx import AsyncClient


SAMPLE_DATASET = [
    {
        "id": "a1",
        "type": "domain",
        "value": "example.com",
        "status": "active",
        "source": "scan",
        "tags": ["root"],
        "metadata": {},
    },
    {
        "id": "a2",
        "type": "subdomain",
        "value": "api.example.com",
        "status": "active",
        "source": "scan",
        "tags": ["prod"],
        "metadata": {},
        "parent": "a1",
    },
    {
        "id": "a3",
        "type": "certificate",
        "value": "CN=api.example.com",
        "status": "active",
        "source": "scan",
        "tags": [],
        "metadata": {"issuer": "Let's Encrypt", "expires": "2025-01-02"},
        "covers": "a2",
    },
]


@pytest.mark.asyncio
async def test_basic_import(async_client: AsyncClient):
    r = await async_client.post("/api/v1/assets/bulk", json=SAMPLE_DATASET)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 3
    assert body["updated"] == 0
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_idempotent_reimport_no_duplicates(async_client: AsyncClient):
    """Importing the same dataset twice must not create duplicate assets."""
    await async_client.post("/api/v1/assets/bulk", json=SAMPLE_DATASET)
    r = await async_client.post("/api/v1/assets/bulk", json=SAMPLE_DATASET)
    body = r.json()

    # Second import: all records should be updates, not new inserts
    assert body["imported"] == 0
    assert body["updated"] == 3
    assert body["errors"] == []

    # Verify count in the DB
    r = await async_client.get("/api/v1/assets/")
    assert r.json()["total"] == 3


@pytest.mark.asyncio
async def test_stale_asset_reactivated_on_resight(async_client: AsyncClient):
    """A stale asset that appears in a new import should flip back to active."""
    await async_client.post("/api/v1/assets/bulk", json=SAMPLE_DATASET)

    # Mark the domain stale
    r = await async_client.get("/api/v1/assets/", params={"value_contains": "example.com", "type": "domain"})
    domain = r.json()["items"][0]
    await async_client.patch(f"/api/v1/assets/{domain['id']}", json={"status": "stale"})

    # Re-import
    await async_client.post("/api/v1/assets/bulk", json=SAMPLE_DATASET)

    # Should be active again
    r = await async_client.get(f"/api/v1/assets/{domain['id']}")
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_metadata_merge_incoming_wins(async_client: AsyncClient):
    """On re-import, incoming metadata fields win over existing ones."""
    initial = [
        {
            "id": "cert1",
            "type": "certificate",
            "value": "CN=merge-test.com",
            "status": "active",
            "source": "scan",
            "tags": [],
            "metadata": {"issuer": "Old CA", "expires": "2024-01-01", "existing_only": "keep"},
        }
    ]
    updated = [
        {
            "id": "cert1",
            "type": "certificate",
            "value": "CN=merge-test.com",
            "status": "active",
            "source": "scan",
            "tags": [],
            "metadata": {"issuer": "New CA", "expires": "2026-01-01"},
        }
    ]

    await async_client.post("/api/v1/assets/bulk", json=initial)
    await async_client.post("/api/v1/assets/bulk", json=updated)

    r = await async_client.get("/api/v1/assets/", params={"value_contains": "merge-test.com"})
    asset = r.json()["items"][0]
    meta = asset["metadata"]

    # Incoming overwrites conflicting keys
    assert meta["issuer"] == "New CA"
    assert meta["expires"] == "2026-01-01"
    # Pre-existing-only key is preserved
    assert meta.get("existing_only") == "keep"


@pytest.mark.asyncio
async def test_tag_union_on_reimport(async_client: AsyncClient):
    """Tags from successive imports are union-merged."""
    initial = [{"id": "t1", "type": "domain", "value": "tags.com", "status": "active", "source": "scan", "tags": ["root"], "metadata": {}}]
    second = [{"id": "t1", "type": "domain", "value": "tags.com", "status": "active", "source": "scan", "tags": ["prod"], "metadata": {}}]

    await async_client.post("/api/v1/assets/bulk", json=initial)
    await async_client.post("/api/v1/assets/bulk", json=second)

    r = await async_client.get("/api/v1/assets/", params={"value_contains": "tags.com"})
    tags = r.json()["items"][0]["tags"]
    assert "root" in tags
    assert "prod" in tags


@pytest.mark.asyncio
async def test_malformed_records_skipped_batch_continues(async_client: AsyncClient):
    """A record with an invalid type must be skipped; valid records still import."""
    batch = [
        {"id": "good1", "type": "domain", "value": "good.com", "status": "active", "source": "scan", "tags": [], "metadata": {}},
        {"id": "bad1", "type": "NOT_A_REAL_TYPE", "value": "bad.com"},  # invalid
        {"id": "good2", "type": "subdomain", "value": "sub.good.com", "status": "active", "source": "scan", "tags": [], "metadata": {}},
    ]
    r = await async_client.post("/api/v1/assets/bulk", json=batch)
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 2
    assert len(body["errors"]) == 1


@pytest.mark.asyncio
async def test_empty_batch_is_safe(async_client: AsyncClient):
    r = await async_client.post("/api/v1/assets/bulk", json=[])
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] == 0
    assert body["updated"] == 0
    assert body["errors"] == []
