import jwt
import httpx

from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException, status
from pydantic import BaseModel


from app.settings import settings


class ShopifySession(BaseModel):
    shop: str
    user_id: str | None = None

    access_token: str | None = None
    expires_in: int | None = None


# =========================================================
# SIMPLE IN-MEMORY TOKEN CACHE
# =========================================================

SHOPIFY_TOKEN_CACHE = {}

# Example structure:
#
# SHOPIFY_TOKEN_CACHE = {
#     "store.myshopify.com": {
#         "access_token": "shpua_xxx",
#         "expires_at": datetime(...)
#     }
# }


async def verify_shopify_token(
    authorization: str = Header(None),
) -> ShopifySession:
    """
    Verify Shopify App Bridge JWT session token
    and exchange it for an expiring offline access token.

    Uses cache to avoid unnecessary token exchanges.
    """

    # =========================================================
    # 1. Validate Authorization Header
    # =========================================================

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    # =========================================================
    # 2. Extract JWT Session Token
    # =========================================================

    session_token = authorization.split(" ")[1]

    try:
        # =========================================================
        # 3. Verify Shopify Session JWT
        # =========================================================

        payload = jwt.decode(
            session_token,
            settings.shopify_api_secret,
            algorithms=["HS256"],
            audience=settings.shopify_api_key,
        )

        # =========================================================
        # 4. Extract Shop Domain
        # =========================================================

        dest = payload.get("dest", "")

        shop_domain = dest.replace("https://", "").replace("http://", "").strip("/")

        if not shop_domain:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Shop domain missing in token",
            )

        # =========================================================
        # 5. CHECK CACHE FIRST
        # =========================================================

        cached = SHOPIFY_TOKEN_CACHE.get(shop_domain)

        now = datetime.now(timezone.utc)

        if cached:
            expires_at = cached.get("expires_at")

            # Add 60-second safety buffer
            if expires_at and expires_at > (now + timedelta(seconds=60)):
                print(f"✅ USING CACHED SHOPIFY TOKEN: {shop_domain}")

                return ShopifySession(
                    shop=shop_domain,
                    user_id=payload.get("sub"),
                    access_token=cached["access_token"],
                    expires_in=int((expires_at - now).total_seconds()),
                )

            else:
                print(f"⚠️ TOKEN EXPIRED: {shop_domain}")

        # =========================================================
        # 6. EXCHANGE SESSION TOKEN
        # =========================================================

        print(f"🔄 EXCHANGING NEW TOKEN: {shop_domain}")

        token_url = f"https://{shop_domain}/admin/oauth/access_token"

        exchange_payload = {
            "client_id": settings.shopify_api_key,
            "client_secret": settings.shopify_api_secret,
            "grant_type": ("urn:ietf:params:oauth:grant-type:token-exchange"),
            "subject_token": session_token,
            "subject_token_type": ("urn:ietf:params:oauth:token-type:id_token"),
            "requested_token_type": (
                "urn:shopify:params:oauth:token-type:offline-access-token"
            ),
            "expiring": "1",
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                token_url,
                data=exchange_payload,
                headers=headers,
            )

        # =========================================================
        # 7. HANDLE TOKEN EXCHANGE FAILURE
        # =========================================================

        if response.status_code != 200:
            print("❌ TOKEN EXCHANGE FAILED")
            print(response.text)

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token exchange failed: {response.text}",
            )

        token_data = response.json()

        print("✅ TOKEN EXCHANGE SUCCESS")
        print(token_data)

        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing exchanged access token",
            )

        # =========================================================
        # 8. TOKEN EXPIRY
        # =========================================================

        expires_in = token_data.get("expires_in", 3600)

        expires_at = now + timedelta(seconds=expires_in)

        # =========================================================
        # 9. SAVE TOKEN TO CACHE
        # =========================================================

        SHOPIFY_TOKEN_CACHE[shop_domain] = {
            "access_token": access_token,
            "expires_at": expires_at,
        }

        print(f"✅ TOKEN CACHED: {shop_domain}")

        # =========================================================
        # 10. RETURN SESSION
        # =========================================================

        return ShopifySession(
            shop=shop_domain,
            user_id=payload.get("sub"),
            access_token=access_token,
            expires_in=expires_in,
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

    except HTTPException:
        raise

    except Exception as e:
        print("❌ SHOPIFY AUTH ERROR")
        print(str(e))

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
