# Import Base and models so Alembic can discover them in target_metadata
from app.models.base import Base
from app.models.asset import Asset, AssetRelationship