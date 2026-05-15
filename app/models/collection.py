from typing import Optional
from sqlalchemy import UniqueConstraint, Index, Column, Text, BigInteger
from sqlmodel import Field

from app.models import BaseModel


class Collection(BaseModel, table=True):
    __tablename__ = "collections"

    __table_args__ = (
        UniqueConstraint(
            "store_id", "shopify_collection_id", name="uq_store_collection"
        ),
        Index("idx_collections_store_id", "store_id"),
    )

    store_id: int = Field(
        foreign_key="stores.id",
        nullable=False,
    )

    shopify_collection_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, index=True),
    )

    title: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )

    handle: Optional[str] = Field(
        default=None,
        sa_column=Column(Text),
    )


class ProductCollection(BaseModel, table=True):  # Keeps the 'id' from BaseModel
    __tablename__ = "product_collections"

    __table_args__ = (
        UniqueConstraint("product_id", "collection_id", name="uq_product_collection"),
    )

    product_id: int = Field(foreign_key="products.id")  # primary_key=True removed
    collection_id: int = Field(foreign_key="collections.id")
