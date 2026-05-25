from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Store


STORE_CACHE = {}


STORE_CACHE = {}


def get_store_id_by_shop_sync(
    shop_domain: str,
    db_session: Session,
) -> int | None:
    if shop_domain in STORE_CACHE:
        return STORE_CACHE[shop_domain]

    stmt = select(Store.id).where(Store.shop_domain == shop_domain)
    result = db_session.execute(stmt)

    store_id = result.scalar_one_or_none()

    if not store_id:
        return None

    STORE_CACHE[shop_domain] = int(store_id)
    return int(store_id)


async def get_store_id_by_shop(
    shop_domain: str,
    db_session: AsyncSession,
) -> int | None:
    if shop_domain in STORE_CACHE:
        return STORE_CACHE[shop_domain]

    stmt = select(Store.id).where(Store.shop_domain == shop_domain)
    result = await db_session.execute(stmt)

    store_id = result.scalar_one_or_none()

    if not store_id:
        return None

    STORE_CACHE[shop_domain] = int(store_id)
    return int(store_id)
