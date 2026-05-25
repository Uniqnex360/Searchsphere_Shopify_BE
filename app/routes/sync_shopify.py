from sqlmodel import Session
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth import ShopifySession, verify_shopify_token
from app.helpers import get_store_id_by_shop_sync
from app.services import create_index, sync_shopify_to_elasticsearch
from app.models import Store
from app.database import get_sync_session

router = APIRouter()


@router.get("/create_index/")
def create_elastic_search_index():
    create_index()
    return {"message": "success"}


@router.post("/sync-data")
@router.post("/sync-data/")
def sync_shopify_to_post_es(
    session: Session = Depends(get_sync_session),
    shopify_session: ShopifySession = Depends(verify_shopify_token),
):
    store_id = get_store_id_by_shop_sync(
        shop_domain=shopify_session.shop, db_session=session
    )
    store = session.execute(
        select(Store).where(Store.id == store_id)
    ).scalar_one_or_none()

    if not store:
        return {
            "status": "error",
            "message": "Store not found",
        }

    sync_shopify_to_elasticsearch(
        session=session,
        store=store,
    )

    return {
        "status": "success",
        "message": "Sync completed",
    }
