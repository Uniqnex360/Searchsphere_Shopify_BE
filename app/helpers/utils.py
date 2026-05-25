from sqlmodel import select, Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Store

# ==========================================
# SIMPLE PYTHON CACHE
# ==========================================

STORE_CACHE = {}


async def get_store_id_by_shop(
    shop_domain: str,
    db_session: AsyncSession,
) -> int | None:
    # ==========================================
    # CACHE HIT
    # ==========================================
    if shop_domain in STORE_CACHE:
        return STORE_CACHE[shop_domain]

    # ==========================================
    # DB FETCH
    # ==========================================
    result = await db_session.exec(
        select(Store.id).where(Store.shop_domain == shop_domain)
    )

    store_id = result.first()

    if not store_id:
        return None

    # ==========================================
    # SAVE CACHE
    # ==========================================
    STORE_CACHE[shop_domain] = int(store_id)

    return int(store_id)


# ==========================================
# SYNC VERSION
# ==========================================


def get_store_id_by_shop_sync(
    shop_domain: str,
    db_session: Session,
) -> int | None:
    """
    Sync version for normal SQLModel Session
    """

    # ==========================================
    # CACHE HIT
    # ==========================================
    if shop_domain in STORE_CACHE:
        return STORE_CACHE[shop_domain]

    # ==========================================
    # DB FETCH
    # ==========================================
    result = db_session.exec(select(Store.id).where(Store.shop_domain == shop_domain))

    store_id = result.first()

    if not store_id:
        return None

    # ==========================================
    # SAVE CACHE
    # ==========================================
    STORE_CACHE[shop_domain] = int(store_id)

    return int(store_id)
