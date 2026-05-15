from sqlmodel import Session, select, delete
from typing import Dict, Any
from app.models.store import Store
from app.models.product import (
    Product,
    ProductImage,
    ProductOption,
)
from app.models.variant import (
    ProductVariant,
    VariantOptionValue,
)
from app.models.collection import (
    Collection,
    ProductCollection,
)

# =========================================================
# DB UPSERT HELPERS
# =========================================================


def get_or_create_product(
    session: Session,
    store_id: int,
    node: Dict[str, Any],
) -> Product:
    shopify_product_id = int(node["id"].split("/")[-1])

    product = session.execute(
        select(Product).where(
            Product.store_id == store_id,
            Product.shopify_product_id == shopify_product_id,
        )
    ).scalar_one_or_none()

    if not product:
        product = Product(
            store_id=store_id,
            shopify_product_id=shopify_product_id,
        )
        session.add(product)

    product.title = node.get("title")
    product.handle = node.get("handle")
    product.vendor = node.get("vendor")
    product.product_type = node.get("productType")
    product.body_html = node.get("descriptionHtml")
    product.status = node.get("status")
    product.tags = node.get("tags", [])
    product.raw_payload = node

    session.flush()
    return product


# =========================================================
# MAIN DB SYNC FUNCTION
# =========================================================


def sync_product_to_database(
    session: Session,
    store: Store,
    node: Dict[str, Any],
):
    try:
        # 1. UPSERT PRODUCT
        product = get_or_create_product(
            session=session,
            store_id=store.id,
            node=node,
        )

        # 2. DELETE OLD RELATIONS
        # We use session.execute(delete(...)) for performance
        session.execute(
            delete(ProductImage).where(ProductImage.product_id == product.id)
        )
        session.execute(
            delete(ProductOption).where(ProductOption.product_id == product.id)
        )

        variant_ids = (
            session.execute(
                select(ProductVariant.id).where(ProductVariant.product_id == product.id)
            )
            .scalars()
            .all()
        )

        if variant_ids:
            session.execute(
                delete(VariantOptionValue).where(
                    VariantOptionValue.variant_id.in_(variant_ids)
                )
            )
            session.execute(
                delete(ProductVariant).where(ProductVariant.id.in_(variant_ids))
            )

        session.execute(
            delete(ProductCollection).where(ProductCollection.product_id == product.id)
        )

        # IMPORTANT: Flush the deletions to the DB
        session.flush()

        # IMPORTANT: Tell SQLAlchemy that 'product' relations are now empty in memory
        session.expire(product)

        # 3. IMAGES
        for img_edge in node.get("images", {}).get("edges", []):
            img_node = img_edge["node"]
            session.add(
                ProductImage(
                    store_id=store.id,
                    product_id=product.id,
                    shopify_image_id=int(img_node["id"].split("/")[-1]),
                    image_url=img_node["url"],
                    alt_text=img_node.get("altText"),
                    width=img_node.get("width"),
                    height=img_node.get("height"),
                )
            )

        # 4. OPTIONS
        for opt in node.get("options", []):
            session.add(
                ProductOption(
                    product_id=product.id,
                    name=opt["name"],
                    position=opt.get("position"),
                )
            )

        # 5. COLLECTIONS
        seen_collections = set()
        for c_edge in node.get("collections", {}).get("edges", []):
            cnode = c_edge["node"]
            shopify_collection_id = int(cnode["id"].split("/")[-1])

            if shopify_collection_id in seen_collections:
                continue
            seen_collections.add(shopify_collection_id)

            collection = session.execute(
                select(Collection).where(
                    Collection.store_id == store.id,
                    Collection.shopify_collection_id == shopify_collection_id,
                )
            ).scalar_one_or_none()

            if not collection:
                collection = Collection(
                    store_id=store.id,
                    shopify_collection_id=shopify_collection_id,
                    title=cnode.get("title"),
                    handle=cnode.get("handle"),
                )
                session.add(collection)
                session.flush()
            else:
                collection.title = cnode.get("title")
                collection.handle = cnode.get("handle")

            # Add link record
            session.add(
                ProductCollection(product_id=product.id, collection_id=collection.id)
            )

        # 6. VARIANTS
        for v_edge in node.get("variants", {}).get("edges", []):
            vnode = v_edge["node"]
            variant = ProductVariant(
                store_id=store.id,
                product_id=product.id,
                shopify_variant_id=int(vnode["id"].split("/")[-1]),
                sku=vnode.get("sku"),
                barcode=vnode.get("barcode"),
                title=vnode.get("title"),
                price=vnode.get("price"),
                compare_at_price=vnode.get("compareAtPrice"),
                inventory_quantity=vnode.get("inventoryQuantity"),
                weight=vnode.get("weight"),
                weight_unit=vnode.get("weightUnit"),
                taxable=vnode.get("taxable"),
                requires_shipping=vnode.get("requiresShipping"),
                position=vnode.get("position"),
                raw_payload=vnode,
            )
            session.add(variant)
            session.flush()

            for opt in vnode.get("selectedOptions", []):
                session.add(
                    VariantOptionValue(
                        variant_id=variant.id,
                        option_name=opt["name"],
                        option_value=opt["value"],
                    )
                )

        session.commit()
        return product

    except Exception as e:
        session.rollback()
        print(f"Error syncing product: {e}")
        raise
