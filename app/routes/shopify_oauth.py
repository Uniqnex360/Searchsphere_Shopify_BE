import secrets
import hashlib
import hmac
import httpx
from urllib.parse import urlencode
from datetime import timezone, datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Store
from app.helpers import utc_now
from app.settings import settings

router = APIRouter()

SHOPIFY_API_KEY = settings.shopify_api_key
SHOPIFY_API_SECRET = settings.shopify_api_secret
SHOPIFY_SCOPES = settings.shopify_scopes
BACKEND_URL = settings.backend_url
FRONTEND_URL = settings.frontend_url

# temporary in-memory state store (replace with Redis in production)
STATE_STORE = set()


def to_naive_utc(dt):
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def verify_hmac(query_params: dict, received_hmac: str) -> bool:
    """
    Shopify requires:
    - remove hmac & signature
    - sort params alphabetically
    - url encode
    """

    filtered = {k: v for k, v in query_params.items() if k not in ["hmac", "signature"]}

    message = urlencode(sorted(filtered.items()), doseq=True)

    generated = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(generated, received_hmac)


@router.get("/shop-status/")
async def check_shop_exists(
    shop: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(select(Store).where(Store.shop_domain == shop))

    store = result.first()

    if not store:
        return {
            "shop": shop,
            "installed": False,
        }

    return {
        "shop": shop,
        "installed": True,
        "active": store.is_active,
    }


@router.get("/auth")
@router.get("/auth/")
async def auth(shop: str):
    if not shop:
        raise HTTPException(status_code=400, detail="Missing shop")

    state = secrets.token_hex(16)
    STATE_STORE.add(state)

    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": f"{BACKEND_URL}/auth/callback",
        "state": state,
    }

    print(params)

    install_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params)}"

    print("install url", install_url)

    return RedirectResponse(install_url)


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    query_params = dict(request.query_params)

    shop = query_params.get("shop")
    host = query_params.get("host")
    code = query_params.get("code")
    received_hmac = query_params.get("hmac")
    state = query_params.get("state")

    if not shop or not code or not received_hmac:
        raise HTTPException(status_code=400, detail="Missing Shopify parameters")

    if state not in STATE_STORE:
        raise HTTPException(status_code=400, detail="Invalid state")

    STATE_STORE.remove(state)

    if not verify_hmac(query_params, received_hmac):
        raise HTTPException(status_code=400, detail="Invalid HMAC")

    token_url = f"https://{shop}/admin/oauth/access_token"

    payload = {
        "client_id": SHOPIFY_API_KEY,
        "client_secret": SHOPIFY_API_SECRET,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, json=payload)

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Token exchange failed: {response.text}",
        )

    token_data = response.json()
    access_token = token_data.get("access_token")
    scope = token_data.get("scope", "")

    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token")

    # -------------------------
    # FIX IS HERE 🔥 (IMPORTANT)
    # -------------------------
    result = await session.exec(select(Store).where(Store.shop_domain == shop))
    store = result.first()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if store:
        store.access_token = access_token
        store.scope = scope
        store.is_active = True
        store.updated_at = now

        session.add(store)  # 🔥 THIS IS THE FIX
    else:
        store = Store(
            shop_domain=shop,
            access_token=access_token,
            scope=scope,
            is_active=True,
            installed_at=to_naive_utc(utc_now()),
            created_at=now,  # 🔥 ADD THIS (CRITICAL)
            updated_at=now,
        )
        session.add(store)

    await session.commit()
    await session.refresh(store)

    return RedirectResponse(
        url=f"{FRONTEND_URL}?shop={shop}&host={host}",
        status_code=302,
    )
