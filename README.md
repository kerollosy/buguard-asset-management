# DarkAtlas Asset Management API
**Buguard Internship Assessment — Backend Engineering Track** **Submitted by:** Kerollos Emad

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker)](https://www.docker.com/)

A REST API acting as the system of record for the DarkAtlas Attack Surface Monitoring (ASM) platform. It ingests discovered assets, handles deduplication, tracks lifecycles, and models the relationship graph between domains, IPs, and technologies.

**Stack:** Python · FastAPI · PostgreSQL · SQLAlchemy (async) · Alembic · Docker Compose

---

## 📋 Table of Contents
- [Quick Start](#-quick-start)
- [Environment Variables](#%EF%B8%8F-environment-variables)
- [Features Implemented](#-features-implemented)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Architecture, Assumptions & Edge Cases](#%EF%B8%8F-architecture-assumptions--edge-cases)

---

## 🚀 Quick Start

The entire stack (API and PostgreSQL database) is fully containerized for easy setup.

### 1. Clone the repository and set up the environment:
Clone and enter the repo:
```bash
git clone https://github.com/kerollosy/buguard-asset-management
cd asset-management
```
Copy the example environment file. The default admin credentials for testing the JWT auth are `admin` / `buguard2026`.
```bash
cp .env.example .env
```
Edit .env if you need custom DB credentials (defaults match docker-compose)

### 2. Start everything (API + PostgreSQL)
```bash
docker-compose up -d --build
```

### 3. Access the API & Documentation
Once the containers are running, the interactive Swagger UI is automatically generated:
* **Base URL:** `http://localhost:8000`
* **Interactive Swagger Docs:** `http://localhost:8000/docs`
* **Redoc:** `http://localhost:8000/redoc`

*(To test write operations in the Swagger UI, click the **Authorize** button at the top right and authenticate using the admin credentials).*

---

## ⚙️ Environment Variables

The application relies on the following environment variables (pre-filled in `.env.example` for easy local testing):

| Variable | Description | Default (Local) |
| :--- | :--- | :--- |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://...` |
| `SECRET_KEY` | Key for signing JWT auth tokens | `super-secret-key...` |
| `ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token validity duration | `60` |
| `ADMIN_USERNAME` | Default admin account | `admin` |
| `ADMIN_PASSWORD` | Default admin password | `buguard2026` |
| `ENVIRONMENT` | Application environment | `development` |

---

## 🔌 API Reference
### Endpoints Summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Health check |
| `GET` | `/api/v1/assets/` | — | List assets with filtering, sorting, pagination |
| `POST` | `/api/v1/assets/` | ✓ | Create a single asset |
| `GET` | `/api/v1/assets/{id}` | — | Get asset by ID |
| `PATCH` | `/api/v1/assets/{id}` | ✓ | Partial update |
| `DELETE` | `/api/v1/assets/{id}` | ✓ | Delete asset (cascades relationships) |
| `POST` | `/api/v1/assets/{id}/stale` | ✓ | Mark asset as stale |
| `POST` | `/api/v1/assets/{id}/tags` | ✓ | Union-merge tags |
| `GET` | `/api/v1/assets/{id}/graph` | — | Asset + immediate relationship graph |
| `POST` | `/api/v1/assets/bulk` | ✓ | Bulk import (idempotent) |
| `POST` | `/api/v1/assets/relationships` | ✓ | Create relationship edge |
| `GET` | `/api/v1/assets/relationships` | — | List relationships (filter by source/target) |
| `DELETE` | `/api/v1/assets/relationships/{id}` | ✓ | Delete relationship |
| `POST` | `/api/v1/auth/token` | — | Login and generate JWT |

### Query Parameters for `GET /api/v1/assets/`

| Param | Type | Description |
|---|---|---|
| `type` | enum | Filter by asset type |
| `status` | enum | Filter by status (`active`, `stale`, `archived`) |
| `tag` | string | Filter assets containing this tag |
| `value_contains` | string | Substring match on asset value |
| `sort_by` | string | `last_seen` (default), `first_seen`, `value`, `type`, `status` |
| `sort_order` | str | `desc` (default), `asc` |
| `page` | int | Page number, 1-indexed |
| `size` | int | Page size, max 100, default 20 |

### Bulk Import Format

`POST /api/v1/assets/bulk` accepts a JSON array matching the DarkAtlas export format:

```json
[
  {
    "id": "a1",
    "type": "domain",
    "value": "example.com",
    "status": "active",
    "source": "scan",
    "tags": ["root"],
    "metadata": {}
  },
  {
    "id": "a2",
    "type": "subdomain",
    "value": "api.example.com",
    "status": "active",
    "source": "scan",
    "tags": ["prod"],
    "metadata": {},
    "parent": "a1"
  },
  {
    "id": "a3",
    "type": "certificate",
    "value": "CN=api.example.com",
    "status": "active",
    "source": "scan",
    "tags": [],
    "metadata": {"issuer": "Let's Encrypt", "expires": "2025-01-02"},
    "covers": "a2"
  }
]
```

Relationship hints (`parent`, `covers`) are processed automatically and turned into relationship edges.

## 🧪 Testing

The project includes a robust, fully asynchronous test suite using `pytest` and `httpx`. Tests are run against a completely isolated database (`darkatlas_test`) to prevent polluting development data.

The test suite validates CRUD logic, complex database filtering, idempotent array merging, and JWT security enforcement across all routes.

Before running it locally, make sure `DATABASE_URL` points to an isolated test database such as `darkatlas_test`.

**To run the tests locally:**
```bash
# 1. Ensure everything is running
docker-compose up -d --build

# 2. Run the test suite
docker compose exec app pytest
```

## ✨ Features Implemented

### Mandatory Requirements
- [x] **Full CRUD Operations:** Support for domains, subdomains, IPs, services, certs, and technologies.
- [x] **Advanced List Endpoint:** Filtering (type, status, tags, value contains), sorting, and pagination.
- [x] **Bulk Import:** Capable of ingesting large JSON payloads.
- [x] **Idempotent Deduplication:** Upserts existing assets, updating `last_seen` and safely merging tags/metadata.
- [x] **Lifecycle Handling:** Tracks `first_seen`, `last_seen`, and status states (`active`, `stale`, `archived`).
- [x] **Relationship Graph:** Manages directed edges (e.g., subdomain -> domain) and retrieves full asset graphs.
- [x] **Authentication:** Stateless JWT (OAuth2) protecting all `POST`, `PATCH`, and `DELETE` routes.
- [x] **Dockerized:** Single command `docker-compose` setup.

### Bonus / Stretch Goals Completed
- [x] **CI Pipeline:** GitHub Actions workflow configured to run the test suite on every push/PR.
- [x] **Rate Limiting:** `slowapi` implemented to protect expensive endpoints (e.g., `/assets/bulk` and list queries).

---

## 🏗️ Architecture, Assumptions & Edge Cases

1. **Two-Tier Authentication (Read vs. Write):**
   Read operations (`GET`) are left open for unhindered internal consumption, while all state-mutating operations (`POST`, `PATCH`, `DELETE`) require a valid Bearer JWT.
2. **PostgreSQL over NoSQL:**
   The schema-less `metadata` field uses `JSONB` for flexible storage, while the core fields maintain relational integrity and support foreign-key constraints on the `asset_relationships` table.
3. **Pydantic V2 Computed Fields:**
   Fields like `is_expired` on certificates are computed at serialization time using `@computed_field`, so the API always returns current temporal state without background jobs.
4. **CI Validation:**
   A GitHub Actions workflow automatically runs the test suite on every push and pull request, so regressions are caught before merge.
5. **Database Indexing:**
   The schema includes indexes for the main lookup and filtering paths, including `(type, value)` uniqueness, `tags`, `status`, and `last_seen`, which keeps deduplication and list queries efficient.
6. **Rate Limiting:**
   `slowapi` is wired into the app to protect heavier endpoints, especially the bulk import route and high-volume list queries.
7. **Authentication Flow:**
   Write operations are protected with JWT via the OAuth2 Password flow. Clients POST credentials to `/api/v1/auth/token`, receive a signed JWT with a configurable expiry, and present it via `Authorization: Bearer <token>` on protected requests.
8. **Deduplication Key:**
   `(type, value)` is the canonical identity of an asset, not the upstream `id` field. The upstream `id` is stored as `external_id` for traceability.
9. **Merge Strategy:**
   Re-seen assets update `last_seen`, union-merge tags, and merge metadata at the top level so incoming keys win while preserving keys that are not present in the new payload.
10. **Partial Success in Bulk Imports:**
   The bulk import route accepts `list[dict]` rather than strict router-level Pydantic validation. If a batch contains one malformed record, valid records are still ingested and the failure is returned in a localized error array instead of dropping the whole request.

### Next Steps

If I were extending this further, the next additions would be:

- **Soft deletes**: instead of hard deletes, set `status = archived` and filter by default
- **Multi-tenancy**: add an `organization_id` column to assets and API keys; scope all queries with a mandatory tenant filter
- **CI pipeline**: GitHub Actions running lint (ruff) + type check (mypy)
- **LangChain feature**: natural-language asset query translating plain English to structured filters
---
