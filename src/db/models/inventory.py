"""ORM models for inventory (3.C): InventorySnapshot."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class InventorySnapshot(Base):
    """Inventory snapshot row (S1: 852 / Value Track style)."""

    __tablename__ = "inventory_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ndc: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    distributor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    snapshot_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))
