import jwt
import requests
from fastapi import HTTPException, Header, status
from pydantic import BaseModel

from app.settings import settings

# Your Shopify Client Secret / API Key (keep this in your .env file)
SHOPIFY_API_KEY = settings.shopify_api_key

# Shopify's official Public Keys URL for verifying session tokens
SHOPIFY_JWKS_URL = "https://api.shopify.com/v2/oauth/public_keys.json"


class ShopifySession(BaseModel):
    shop: str
    user_id: int | None = None


def get_shopify_public_keys():
    try:
        response = requests.get(SHOPIFY_JWKS_URL)
        response.raise_for_status()
        return response.json()["keys"]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Shopify public keys: {str(e)}",
        )


def verify_shopify_token(authorization: str = Header(None)) -> ShopifySession:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    # Extract the raw token string
    token = authorization.split(" ")[1]

    try:
        # 1. Unverified decode just to grab the 'kid' (Key ID) from the header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # 2. Find the matching public key from Shopify's keys
        public_keys = get_shopify_public_keys()
        matching_key = next((key for key in public_keys if key["kid"] == kid), None)

        if not matching_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signing key",
            )

        # 3. Construct the public key structure using PyJWT
        jwk = jwt.algorithms.RSAAlgorithm.from_jwk(matching_key)

        # 4. Fully decode and verify the cryptographic signature and expiration time
        payload = jwt.decode(
            token,
            jwk,
            algorithms=["RS256"],
            audience=SHOPIFY_API_KEY,  # Must match your App API Key
        )

        # 5. Extract the shop domain (contained in 'dest' claim) and user metadata
        # Shopify JWTs contain 'dest' which looks like "https://your-store.myshopify.com"
        dest_url = payload.get("dest", "")
        shop_domain = dest_url.replace("https://", "").strip("/")

        if not shop_domain:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Shop destination missing in token claims",
            )

        return ShopifySession(
            shop=shop_domain,
            user_id=payload.get("sub"),  # Optional: unique ID of the staff member
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Shopify session token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Shopify session token: {str(e)}",
        )
