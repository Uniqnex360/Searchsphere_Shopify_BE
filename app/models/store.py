from typing import Optional
from datetime import datetime

from sqlmodel import Field
from sqlalchemy import Column, DateTime

from app.models.common.base import BaseModel
from app.helpers import utc_now


class Store(BaseModel, table=True):
    """Shopify store model."""

    __tablename__ = "stores"

    shopify_store_id: Optional[int] = Field(
        default=None,
        index=True,
        unique=True,
        nullable=True,
    )

    shop_domain: str = Field(
        index=True,
        unique=True,
        nullable=False,
        max_length=255,
    )

    access_token: str = Field(
        nullable=False,
    )

    scope: Optional[str] = Field(
        default=None,
        nullable=True,
    )

    installed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        default_factory=utc_now,
    )
