from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import (
    Product,
    ProductImage,
    ProductOption,
    ProductVariant,
    VariantOptionValue,
    Collection,
    ProductCollection,
)


# =========================================================
# PRODUCT DETAIL (SQLALCHEMY ORM VERSION)
# =========================================================
def build_product_response(product: Product, session: Session):
    # =====================================================
    # IMAGES
    # =====================================================
    images = (
        session.execute(
            select(ProductImage).where(ProductImage.product_id == product.id)
        )
        .scalars()
        .all()
    )

    # =====================================================
    # OPTIONS
    # =====================================================
    options = (
        session.execute(
            select(ProductOption).where(ProductOption.product_id == product.id)
        )
        .scalars()
        .all()
    )

    # =====================================================
    # VARIANTS
    # =====================================================
    variants = (
        session.execute(
            select(ProductVariant).where(ProductVariant.product_id == product.id)
        )
        .scalars()
        .all()
    )

    variant_ids = [v.id for v in variants]

    # =====================================================
    # VARIANT OPTION VALUES (batch fetch)
    # =====================================================
    option_values = []
    if variant_ids:
        option_values = (
            session.execute(
                select(VariantOptionValue).where(
                    VariantOptionValue.variant_id.in_(variant_ids)
                )
            )
            .scalars()
            .all()
        )

    # group option values by variant_id (faster lookup)
    option_map = {}
    for ov in option_values:
        option_map.setdefault(ov.variant_id, []).append(ov)

    # =====================================================
    # COLLECTIONS (via mapping table)
    # =====================================================
    product_collections = (
        session.execute(
            select(ProductCollection).where(ProductCollection.product_id == product.id)
        )
        .scalars()
        .all()
    )

    collection_ids = [pc.collection_id for pc in product_collections]

    collections = []
    if collection_ids:
        collections = (
            session.execute(select(Collection).where(Collection.id.in_(collection_ids)))
            .scalars()
            .all()
        )

    # =====================================================
    # FINAL RESPONSE
    # =====================================================
    return {
        "id": product.id,
        "store_id": product.store_id,
        "shopify_product_id": product.shopify_product_id,
        "title": product.title,
        "handle": product.handle,
        "vendor": product.vendor,
        "product_type": product.product_type,
        "body_html": product.body_html,
        "status": product.status,
        "published_at": product.published_at,
        "tags": product.tags,
        "raw_payload": product.raw_payload,
        # -------------------------
        # IMAGES
        # -------------------------
        "images": [
            {
                "id": img.id,
                "image_url": img.image_url,
                "alt_text": img.alt_text,
                "position": img.position,
                "width": img.width,
                "height": img.height,
            }
            for img in images
        ],
        # -------------------------
        # OPTIONS
        # -------------------------
        "options": [
            {
                "id": opt.id,
                "name": opt.name,
                "position": opt.position,
            }
            for opt in options
        ],
        # -------------------------
        # VARIANTS + OPTION VALUES
        # -------------------------
        "variants": [
            {
                "id": var.id,
                "shopify_variant_id": var.shopify_variant_id,
                "sku": var.sku,
                "barcode": var.barcode,
                "title": var.title,
                "price": str(var.price) if var.price else None,
                "compare_at_price": (
                    str(var.compare_at_price) if var.compare_at_price else None
                ),
                "inventory_quantity": var.inventory_quantity,
                "weight": str(var.weight) if var.weight else None,
                "weight_unit": var.weight_unit,
                "taxable": var.taxable,
                "requires_shipping": var.requires_shipping,
                "position": var.position,
                "option_values": [
                    {
                        "id": ov.id,
                        "option_name": ov.option_name,
                        "option_value": ov.option_value,
                    }
                    for ov in option_map.get(var.id, [])
                ],
            }
            for var in variants
        ],
        # -------------------------
        # COLLECTIONS
        # -------------------------
        "collections": [
            {
                "id": col.id,
                "title": col.title,
                "handle": col.handle,
                "shopify_collection_id": col.shopify_collection_id,
            }
            for col in collections
        ],
    }
