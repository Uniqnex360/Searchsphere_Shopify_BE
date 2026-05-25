from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from elasticsearch import Elasticsearch

from app.database import get_session
from app.helpers import get_es, get_store_id_by_shop
from app.models import Product
from app.auth import ShopifySession, verify_shopify_token

router = APIRouter()


# -----------------------------
# DATE RANGE HELPER
# -----------------------------
def get_day_range(date: datetime):
    start = datetime(date.year, date.month, date.day, 0, 0, 0)
    end = start + timedelta(days=1)
    return start, end


# -----------------------------
# SIMPLE DASHBOARD API
# -----------------------------
@router.get("/dashboard/summary/")
async def dashboard_summary(
    db: AsyncSession = Depends(get_session),
    es: Elasticsearch = Depends(get_es),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    session: ShopifySession = Depends(verify_shopify_token),
):
    # =====================================
    # GET STORE ID
    # =====================================
    store_id = await get_store_id_by_shop(shop_domain=session.shop)

    if not store_id:
        raise HTTPException(
            status_code=404,
            detail="Store not found",
        )

    # =====================================
    # PRODUCTS COUNT (POSTGRES)
    # =====================================
    query = (
        select(func.count()).select_from(Product).where(Product.store_id == store_id)
    )

    if start_date:
        start_date, _ = get_day_range(start_date)

        query = query.where(Product.created_at >= start_date)

    if end_date:
        _, end_date = get_day_range(end_date)

        query = query.where(Product.created_at < end_date)

    total_products = (await db.exec(query)).scalar()

    # =====================================
    # ELASTICSEARCH DOC COUNT
    # =====================================
    try:
        es_count_resp = es.count(
            index="products",
            body={"query": {"term": {"store_id": store_id}}},
        )

        total_es_docs = es_count_resp.get(
            "count",
            0,
        )

    except Exception:
        total_es_docs = 0

    # =====================================
    # RESPONSE
    # =====================================
    return {
        "store_id": store_id,
        "total_products": total_products,
        "total_es_docs": total_es_docs,
    }
