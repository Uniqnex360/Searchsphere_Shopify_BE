from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

import base64
import hmac
import hashlib
import json
from fastapi import Header, HTTPException
from app.settings import settings
from app.database import get_session
from app.routes import routers

SHOPIFY_API_SECRET = settings.shopify_api_secret
SHOPIFY_API_KEY = settings.shopify_api_key


app = FastAPI(title="Search Sphere Shopify", root_path="/shopify")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ allow everything
    allow_credentials=False,  # ❗ must be False if using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in routers:
    app.include_router(r)

# ✅ NOW inspect real routes
# for route in app.routes:
#     if hasattr(route, "path"):
#         print(route.path, getattr(route, "name", None))


@app.get("/test-db/")
async def test_db(session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text("SELECT 1"))
        return {"status": "success", "value": result.scalar()}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def base64url_decode(data: str):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def verify_shopify_jwt(token: str):
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")

        # header = json.loads(base64url_decode(header_b64))
        payload = json.loads(base64url_decode(payload_b64))

        signed_data = f"{header_b64}.{payload_b64}".encode()

        expected_signature = hmac.new(
            SHOPIFY_API_SECRET.encode(), signed_data, hashlib.sha256
        ).digest()

        actual_signature = base64url_decode(signature_b64)

        if not hmac.compare_digest(expected_signature, actual_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # -------------------------
        # VERIFY ISS (Shopify app)
        # -------------------------
        if payload.get("iss") is None:
            raise HTTPException(status_code=401, detail="Missing iss")

        # -------------------------
        # VERIFY DEST (VERY IMPORTANT)
        # -------------------------
        dest = payload.get("dest", "")
        if SHOPIFY_API_KEY not in dest:
            raise HTTPException(status_code=401, detail="Invalid dest")

        # -------------------------
        # VERIFY EXPIRY
        # -------------------------
        import time

        if payload.get("exp", 0) < time.time():
            raise HTTPException(status_code=401, detail="Token expired")

        return payload

    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


# -------------------------
# SIMPLE TEST API
# -------------------------
@app.get("/verify")
async def verify_token(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.replace("Bearer ", "")

    payload = verify_shopify_jwt(token)

    return {
        "status": "ok",
        "shop": payload.get("dest"),
        "user": payload.get("sub"),
    }
