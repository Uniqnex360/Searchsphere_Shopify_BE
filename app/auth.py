import jwt
from fastapi import HTTPException, Header, status
from pydantic import BaseModel

from app.settings import settings

SHOPIFY_API_KEY = settings.shopify_api_key
SHOPIFY_API_SECRET = settings.shopify_api_secret


class ShopifySession(BaseModel):
    shop: str
    user_id: int | None = None


def verify_shopify_token(authorization: str = Header(None)) -> ShopifySession:
    """
    Verify Shopify App Bridge session token (JWT - HS256)
    """

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.split(" ")[1]

    try:
        # ✅ Decode + verify Shopify session token (HS256)
        payload = jwt.decode(
            token,
            SHOPIFY_API_SECRET,
            algorithms=["HS256"],
            audience=SHOPIFY_API_KEY,
        )

        # Shopify sends shop in "dest"
        dest = payload.get("dest", "")

        shop_domain = dest.replace("https://", "").replace("http://", "").strip("/")

        if not shop_domain:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Shop domain missing in token",
            )

        return ShopifySession(
            shop=shop_domain,
            user_id=payload.get("sub"),
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Shopify session token expired",
        )

    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Shopify session token: {str(e)}",
        )
