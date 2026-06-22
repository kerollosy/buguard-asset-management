import logging
import uvicorn
from fastapi import FastAPI

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DarkAtlas Asset Management API",
    description=(
        "The asset inventory module of the DarkAtlas Attack Surface Monitoring platform. "
        "Tracks domains, subdomains, IPs, services, certificates, and technologies. "
        "With deduplication, lifecycle management, and a relationship graph."
    ),
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health", tags=["Health"], summary="Health check")
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)