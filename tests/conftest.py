import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.models.base import Base

# Point to the dedicated test database we created
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/darkatlas_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)

async def override_get_db():
    """Override dependency to yield sessions from the test database."""
    async with TestingSessionLocal() as session:
        yield session

# Inject the override
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Builds the database tables before the test suite runs, and drops them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clear_db_data(setup_database):
    """
    Clears all data from all tables before every individual test.
    Requires 'setup_database' to ensure tables actually exist first.
    """
    async with test_engine.begin() as conn:
        # Loop through tables in reverse topological order to respect foreign keys
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture(scope="session")
async def async_client():
    """Provides an asynchronous HTTPX client routing to our FastAPI app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client