from sqlmodel import Session
from fastapi import APIRouter, Depends
from sqlalchemy import select

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
):
    store = session.execute(select(Store).where(Store.id == 4)).scalar_one_or_none()

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
