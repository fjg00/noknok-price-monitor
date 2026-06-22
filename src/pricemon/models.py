"""SQLAlchemy ORM models for stores, products, and price history."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    is_base: Mapped[bool] = mapped_column(default=False)

    products: Mapped[list["Product"]] = relationship(back_populates="store")


class Product(Base):
    """A product as listed by a single store."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("store_id", "external_id", name="uq_store_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    brand: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Normalized text used by the fuzzy matcher.
    norm_key: Mapped[str] = mapped_column(String(256), index=True, default="")

    store: Mapped["Store"] = relationship(back_populates="products")
    prices: Mapped[list["PricePoint"]] = relationship(back_populates="product")


class PricePoint(Base):
    """A single observed price for a product at a point in time."""

    __tablename__ = "price_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    in_stock: Mapped[bool] = mapped_column(default=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    product: Mapped["Product"] = relationship(back_populates="prices")


class Match(Base):
    """A fuzzy link between a NokNok product and a competitor product."""

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("base_product_id", "competitor_product_id", name="uq_match"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    base_product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    competitor_product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), index=True
    )
    score: Mapped[float] = mapped_column(Float)  # 0-100 fuzzy confidence
    confirmed: Mapped[bool] = mapped_column(default=False)  # human-reviewed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
