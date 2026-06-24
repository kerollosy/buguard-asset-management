import logging

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler

from app.core.limiter import limiter
from app.routers import assets, auth, bulk, relationships
from app.core.config import settings

logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Premium OpenAPI Tags for Swagger UI
openapi_tags = [
    {
        "name": "Assets",
        "description": "Core asset inventory operations. Create, search, update, and manage the lifecycle of discovered attack surface assets.",
    },
    {
        "name": "Relationships",
        "description": "Manage the graph of connections between assets (e.g., subdomains resolving to IPs, certificates covering domains).",
    },
    {
        "name": "Bulk Import",
        "description": "High-performance, idempotent data ingestion with automatic deduplication.",
    },
    {
        "name": "Authentication",
        "description": "OAuth2 authentication and security access token management.",
    },
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "The asset inventory module of the DarkAtlas Attack Surface Monitoring platform. "
        "Tracks domains, subdomains, IPs, services, certificates, and technologies. "
        "Includes advanced deduplication, lifecycle management, and a relationship graph."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # type: ignore


@app.get("/health", tags=["Health"], summary="System Health Check")
async def check_health():
    """Verify that the API and environment are running correctly."""
    return {"status": "ok", "environment": settings.ENVIRONMENT}

# Including Routers and linking them to their corresponding OpenAPI tags
app.include_router(relationships.router, prefix="/assets", tags=["Relationships"])
app.include_router(assets.router, prefix="/assets", tags=["Assets"])
app.include_router(bulk.router, prefix="/assets", tags=["Bulk Import"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
