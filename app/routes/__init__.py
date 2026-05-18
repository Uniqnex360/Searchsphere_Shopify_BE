# ruff: noqa: F401
from .sync_shopify import router as sync_shopify
from .product import router as product
from .shopify_oauth import router as shopify_oauth
from .gdpr import router as gdpr

routers = [sync_shopify, product, shopify_oauth, gdpr]
