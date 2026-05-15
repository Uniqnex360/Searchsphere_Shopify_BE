from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    BigInteger,
    Text,
    UniqueConstraint,
    Index,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlmodel import Field

from app.models import BaseModel


class Product(BaseModel, table=True):
    __tablename__ = "products"

    __table_args__ = (
        UniqueConstraint("store_id", "shopify_product_id", name="uq_store_product"),
        Index("idx_products_store_id", "store_id"),
        Index("idx_products_vendor", "vendor"),
        Index("idx_products_product_type", "product_type"),
        Index("idx_products_status", "status"),
        Index("idx_products_handle", "handle"),
    )

    store_id: int = Field(
        foreign_key="stores.id",
        nullable=False,
    )

    shopify_product_id: int = Field(
        sa_column=Column(BigInteger, nullable=False, index=True),
    )

    title: str = Field(
        sa_column=Column(Text, nullable=False, index=True),
    )

    handle: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    vendor: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    product_type: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    body_html: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    status: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    published_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )

    tags: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(ARRAY(Text)),
    )

    raw_payload: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB),
    )


class ProductImage(BaseModel, table=True):
    __tablename__ = "product_images"

    __table_args__ = (Index("idx_images_product_id", "product_id"),)

    store_id: int = Field(
        foreign_key="stores.id",
        nullable=False,
    )

    product_id: int = Field(
        foreign_key="products.id",
        nullable=False,
    )

    shopify_image_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, index=True),
    )

    image_url: str = Field(
        sa_column=Column(Text, nullable=False),
    )

    alt_text: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    position: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer),
    )

    width: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer),
    )

    height: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer),
    )


class ProductOption(BaseModel, table=True):
    __tablename__ = "product_options"

    __table_args__ = (Index("idx_product_options_product_id", "product_id"),)

    product_id: int = Field(
        foreign_key="products.id",
        nullable=False,
    )

    name: str = Field(
        sa_column=Column(Text, nullable=False),
    )

    position: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer),
    )
