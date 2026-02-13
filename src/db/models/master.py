"""ORM models for master/reference data (3.B): Location, Distributor, Product, Customer, Contact."""

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin


class Location(Base, TimestampMixin):
    """Location (S1 lookup)."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Distributor(Base, TimestampMixin):
    """Distributor (S1, S2, S3)."""

    __tablename__ = "distributors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="distributor")


class Product(Base, TimestampMixin):
    """Product / NDC (S1, S2, S3)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ndc: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Customer(Base, TimestampMixin):
    """Customer (S2: Class of Trade, REMS, 340B)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    dea_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    class_of_trade: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rems_certified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_340b: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ldn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    distributor_id: Mapped[int | None] = mapped_column(ForeignKey("distributors.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    distributor: Mapped["Distributor | None"] = relationship("Distributor", back_populates="customers")
    contacts: Mapped[list["Contact"]] = relationship("Contact", back_populates="customer")


class Contact(Base, TimestampMixin):
    """Contact linked to a customer (S2)."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="contacts")
