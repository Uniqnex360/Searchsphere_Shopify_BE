# ruff: noqa: F401
from .sync_shopify import router as sync_shopify
from .product import router as product

routers = [sync_shopify, product]
