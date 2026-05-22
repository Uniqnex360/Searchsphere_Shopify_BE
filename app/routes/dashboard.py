from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from elasticsearch import Elasticsearch

from app.database import get_session
from app.helpers import get_es
from app.models import Product

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
):
    # -----------------------------
    # PRODUCTS COUNT
    # -----------------------------
    query = select(func.count()).select_from(Product)

    if start_date:
        start_date, _ = get_day_range(start_date)
        query = query.where(Product.created_at >= start_date)

    if end_date:
        _, end_date = get_day_range(end_date)
        query = query.where(Product.created_at < end_date)

    total_products = (await db.exec(query)).scalar()

    # -----------------------------
    # ELASTICSEARCH DOC COUNT
    # -----------------------------
    try:
        es_count_resp = es.count(index="products")
        total_es_docs = es_count_resp.get("count", 0)
    except Exception:
        total_es_docs = 0

    # -----------------------------
    # RESPONSE
    # -----------------------------
    return {
        "total_products": total_products,
        "total_es_docs": total_es_docs,
    }
