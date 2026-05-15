from typing import Optional
from decimal import Decimal
from sqlalchemy import (
    Column,
    BigInteger,
    Text,
    UniqueConstraint,
    Index,
    Numeric,
    Integer,
    Boolean,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models import BaseModel


class ProductVariant(BaseModel, table=True):
    __tablename__ = "product_variants"

    __table_args__ = (
        UniqueConstraint("store_id", "shopify_variant_id", name="uq_store_variant"),
        Index("idx_variants_store_id", "store_id"),
        Index("idx_variants_product_id", "product_id"),
        Index("idx_variants_sku", "sku"),
        Index("idx_variants_barcode", "barcode"),
    )

    store_id: int = Field(
        foreign_key="stores.id",
        nullable=False,
    )

    product_id: int = Field(
        foreign_key="products.id",
        nullable=False,
    )

    shopify_variant_id: int = Field(
        sa_column=Column(BigInteger, nullable=False, index=True),
    )

    sku: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    barcode: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    title: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(12, 2)),
    )

    compare_at_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(12, 2)),
    )

    inventory_quantity: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer),
    )

    weight: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(10, 2)),
    )

    weight_unit: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    taxable: Optional[bool] = Field(
        default=None,
        sa_column=Column(Boolean),
    )

    requires_shipping: Optional[bool] = Field(
        default=None,
        sa_column=Column(Boolean),
    )

    position: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer),
    )

    raw_payload: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB),
    )


class VariantOptionValue(BaseModel, table=True):
    __tablename__ = "variant_option_values"

    __table_args__ = (Index("idx_variant_option_variant_id", "variant_id"),)

    variant_id: int = Field(
        foreign_key="product_variants.id",
        nullable=False,
    )

    option_name: str = Field(
        sa_column=Column(Text, nullable=False),
    )

    option_value: str = Field(
        sa_column=Column(Text, nullable=False),
    )
