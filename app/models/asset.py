import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Enum,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AssetType(str, enum.Enum):
    domain = "domain"
    subdomain = "subdomain"
    ip_address = "ip_address"
    service = "service"
    certificate = "certificate"
    technology = "technology"


class AssetStatus(str, enum.Enum):
    active = "active"
    stale = "stale"
    archived = "archived"


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    # E.g., "resolves_to", "covers", "runs_on"
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    source_asset: Mapped["Asset"] = relationship(
        "Asset", foreign_keys=[source_id], back_populates="outgoing"
    )
    target_asset: Mapped["Asset"] = relationship(
        "Asset", foreign_keys=[target_id], back_populates="incoming"
    )

    __table_args__ = (
        # Prevent duplicate edges of the same type between the same two assets
        UniqueConstraint(
            "source_id", "target_id", "relationship_type",
            name="uq_relationship_source_target_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AssetRelationship {self.source_id} "
            f"--[{self.relationship_type}]--> {self.target_id}>"
        )


class Asset(Base):
    """
    Core asset model storing discovered internet-facing assets.
    """
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # The original ID from the upstream scan/import — stored for traceability
    # but NOT used as the dedup key (type + value is canonical).
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    type: Mapped[AssetType] = mapped_column(Enum(AssetType), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), nullable=False, default=AssetStatus.active)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    # Timestamps
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    # Named "asset_metadata" in Python to avoid collision with SQLAlchemy's
    # built-in .metadata class attribute on the Base.
    asset_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    # Relationships (ORM)
    outgoing: Mapped[list["AssetRelationship"]] = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.source_id",
        back_populates="source_asset",
        cascade="all, delete-orphan",
    )
    incoming: Mapped[list["AssetRelationship"]] = relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.target_id",
        back_populates="target_asset",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Deduplication key: (type, value) must be globally unique
        UniqueConstraint("type", "value", name="uq_asset_type_value"),

        # GIN index on tags for fast array overlap queries
        Index("ix_assets_tags", "tags", postgresql_using="gin"),
        
        Index("ix_asset_status", "status"),
        Index("ix_asset_last_seen", "last_seen"),
    )

    def __repr__(self) -> str:
        return f"<Asset id={self.id} type={self.type} value={self.value!r}>"
