"""ORM models for allocation (3.D): AllocationRule, AllocationRecord, SpecBuyReport, DataDictionary."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin


class AllocationRule(Base, TimestampMixin):
    """Allocation rule (DCS-style: NDC, year, allocation %, brand)."""

    __tablename__ = "allocation_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ndc: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    distributor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    allocation_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class AllocationRecord(Base, TimestampMixin):
    """Allocation record (quantity allocated/used)."""

    __tablename__ = "allocation_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ndc: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    distributor: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quantity_allocated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SpecBuyReport(Base):
    """Spec-buy report row (purchase, dispense, build, burn, WAC)."""

    __tablename__ = "spec_buy_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ndc: Mapped[str] = mapped_column(String(32), nullable=False)
    distributor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase: Mapped[float | None] = mapped_column(Float, nullable=True)
    dispense: Mapped[float | None] = mapped_column(Float, nullable=True)
    build: Mapped[float | None] = mapped_column(Float, nullable=True)
    burn: Mapped[float | None] = mapped_column(Float, nullable=True)
    wac: Mapped[float | None] = mapped_column(Float, nullable=True)
    spec_buy_dollar: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.now(timezone.utc))


class DataDictionary(Base, TimestampMixin):
    """Data dictionary (which dashboard/report/data source)."""

    __tablename__ = "data_dictionary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    endpoint_or_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    schema_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
