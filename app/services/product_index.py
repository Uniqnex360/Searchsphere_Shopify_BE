from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from sqlmodel import Session

import re
import html

from app.helpers import get_es, fetch_shopify_products
from app.services.sync_product_db import sync_product_to_database
from app.models import Store

# =========================================================
# ELASTICSEARCH CLIENT
# =========================================================

es = get_es()

INDEX_ALIAS = "products"
INDEX_NAME_V1 = "products_v1"


# =========================================================
# EMBEDDING MODEL
# =========================================================

embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


# =========================================================
# INDEX MAPPING
# =========================================================

mapping = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "refresh_interval": "1s",
        "max_ngram_diff": 20,
        "analysis": {
            "char_filter": {
                "special_char_mapping": {
                    "type": "mapping",
                    "mappings": [
                        "- => ",
                        "_ => ",
                        ". => ",
                    ],
                }
            },
            "filter": {
                "autocomplete_filter": {
                    "type": "edge_ngram",
                    "min_gram": 2,
                    "max_gram": 20,
                },
                "synonym_filter": {
                    "type": "synonym",
                    "synonyms": [
                        "shoe, sneaker",
                        "tshirt, tee",
                        "mobile, phone",
                        "hoodie, sweatshirt",
                        "trouser, pants",
                    ],
                },
            },
            "analyzer": {
                "autocomplete": {
                    "type": "custom",
                    "char_filter": ["special_char_mapping"],
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "asciifolding",
                        "autocomplete_filter",
                    ],
                },
                "english_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": [
                        "lowercase",
                        "asciifolding",
                        "synonym_filter",
                        "porter_stem",
                    ],
                },
            },
        },
    },
    "mappings": {
        "dynamic": False,
        "properties": {
            # =================================================
            # CORE IDS
            # =================================================
            "id": {"type": "long"},
            "store_id": {"type": "long"},
            "shopify_product_id": {"type": "long"},
            # =================================================
            # PRODUCT INFO
            # =================================================
            "title": {
                "type": "text",
                "analyzer": "english_analyzer",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                    },
                    "autocomplete": {
                        "type": "text",
                        "analyzer": "autocomplete",
                        "search_analyzer": "standard",
                    },
                    "suggest": {
                        "type": "search_as_you_type",
                    },
                },
            },
            "title_normalized": {
                "type": "keyword",
            },
            "vendor": {
                "type": "text",
                "fields": {
                    "keyword": {
                        "type": "keyword",
                    }
                },
            },
            "vendor_normalized": {
                "type": "keyword",
            },
            "product_type": {
                "type": "keyword",
            },
            "handle": {
                "type": "keyword",
            },
            "body_html": {
                "type": "text",
                "analyzer": "english_analyzer",
            },
            "status": {
                "type": "keyword",
            },
            "tags": {
                "type": "keyword",
            },
            # =================================================
            # COLLECTIONS
            # =================================================
            "collections": {
                "type": "nested",
                "properties": {
                    "id": {"type": "long"},
                    "title": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                            }
                        },
                    },
                    "handle": {
                        "type": "keyword",
                    },
                },
            },
            # =================================================
            # IMAGES
            # =================================================
            "images": {
                "type": "nested",
                "properties": {
                    "url": {
                        "type": "keyword",
                    },
                    "alt_text": {
                        "type": "text",
                    },
                },
            },
            # =================================================
            # OPTIONS
            # =================================================
            "options": {
                "type": "nested",
                "properties": {
                    "name": {
                        "type": "keyword",
                    },
                    "position": {
                        "type": "integer",
                    },
                },
            },
            # =================================================
            # VARIANTS
            # =================================================
            "variants": {
                "type": "nested",
                "properties": {
                    "id": {"type": "long"},
                    "shopify_variant_id": {"type": "long"},
                    "sku": {
                        "type": "keyword",
                    },
                    "barcode": {
                        "type": "keyword",
                    },
                    "title": {
                        "type": "text",
                        "analyzer": "english_analyzer",
                    },
                    "price": {
                        "type": "float",
                    },
                    "compare_at_price": {
                        "type": "float",
                    },
                    "inventory_quantity": {
                        "type": "integer",
                    },
                    "weight": {
                        "type": "float",
                    },
                    "weight_unit": {
                        "type": "keyword",
                    },
                    "taxable": {
                        "type": "boolean",
                    },
                    "requires_shipping": {
                        "type": "boolean",
                    },
                    "position": {
                        "type": "integer",
                    },
                    "option_values": {
                        "type": "nested",
                        "properties": {
                            "option_name": {
                                "type": "keyword",
                            },
                            "option_value": {
                                "type": "keyword",
                            },
                        },
                    },
                },
            },
            # =================================================
            # FLATTENED SEARCH FIELDS
            # =================================================
            "all_skus": {
                "type": "keyword",
            },
            "all_barcodes": {
                "type": "keyword",
            },
            "all_option_values": {
                "type": "keyword",
            },
            "search_text": {
                "type": "text",
                "analyzer": "english_analyzer",
            },
            # =================================================
            # SEARCH SUGGESTION
            # =================================================
            "suggest": {
                "type": "completion",
            },
            # =================================================
            # FILTERING / FACETS
            # =================================================
            "min_price": {
                "type": "float",
            },
            "max_price": {
                "type": "float",
            },
            "total_inventory": {
                "type": "integer",
            },
            "in_stock": {
                "type": "boolean",
            },
            # =================================================
            # RANKING
            # =================================================
            "popularity_score": {
                "type": "float",
            },
            "view_count": {
                "type": "integer",
            },
            "purchase_count": {
                "type": "integer",
            },
            "cart_count": {
                "type": "integer",
            },
            "conversion_score": {
                "type": "float",
            },
            "discount_percentage": {
                "type": "float",
            },
            # =================================================
            # VECTOR SEARCH
            # =================================================
            "embedding": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine",
            },
            "embedding_model": {
                "type": "keyword",
            },
        },
    },
}


# =========================================================
# CREATE INDEX
# =========================================================


def create_index():
    if es.indices.exists(index=INDEX_NAME_V1):
        print("Index already exists")
        return

    es.indices.create(
        index=INDEX_NAME_V1,
        body=mapping,
    )

    # Create alias
    es.indices.put_alias(
        index=INDEX_NAME_V1,
        name=INDEX_ALIAS,
    )

    print("Index created")


# =========================================================
# HELPERS
# =========================================================


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def generate_embedding(text: str) -> List[float]:
    return embedding_model.encode(text).tolist()


def transform_shopify_product(node: Dict[str, Any]):
    class Obj:
        pass

    def gid(x):
        return int(x.split("/")[-1])

    product = Obj()
    product.id = gid(node["id"])
    product.store_id = 1
    product.shopify_product_id = product.id

    product.title = node.get("title")
    product.handle = node.get("handle")
    product.vendor = node.get("vendor")
    product.product_type = node.get("productType")
    product.body_html = node.get("descriptionHtml")
    product.status = node.get("status")
    product.tags = node.get("tags", [])

    # ---------------- images ----------------
    images = [Obj() for _ in node.get("images", {}).get("edges", [])]
    for obj, edge in zip(images, node["images"]["edges"]):
        obj.image_url = edge["node"]["url"]
        obj.alt_text = edge["node"]["altText"]

    # ---------------- options ----------------
    options = []
    for o in node.get("options", []):
        opt = Obj()
        opt.name = o["name"]
        opt.position = o["position"]
        options.append(opt)

    # ---------------- collections ----------------
    collections = []
    for c in node.get("collections", {}).get("edges", []):
        col = Obj()
        col.id = gid(c["node"]["id"])
        col.title = c["node"]["title"]
        col.handle = c["node"]["handle"]
        collections.append(col)

    # ---------------- variants ----------------
    variants = []
    variant_map = {}

    for v in node.get("variants", {}).get("edges", []):
        vnode = v["node"]

        var = Obj()
        var.id = gid(vnode["id"])
        var.shopify_variant_id = var.id
        var.title = vnode.get("title")
        var.sku = vnode.get("sku")
        var.barcode = vnode.get("barcode")
        var.price = vnode.get("price")
        var.compare_at_price = vnode.get("compareAtPrice")
        var.inventory_quantity = vnode.get("inventoryQuantity", 0)
        var.position = vnode.get("position")

        variant_map[var.id] = []

        for opt in vnode.get("selectedOptions", []):
            o = Obj()
            o.option_name = opt["name"]
            o.option_value = opt["value"]
            variant_map[var.id].append(o)

        variants.append(var)

    return {
        "product": product,
        "variants": variants,
        "images": images,
        "options": options,
        "collections": collections,
        "variant_option_values_map": variant_map,
    }


def build_product_document(
    product,
    variants,
    images,
    options,
    collections,
    variant_option_values_map,
    store,
) -> Dict[str, Any]:
    all_skus = []
    all_option_values = []
    prices = []
    total_inventory = 0

    variant_docs = []

    for v in variants:
        if v.sku:
            all_skus.append(v.sku)

        if v.price:
            prices.append(float(v.price))

        total_inventory += v.inventory_quantity or 0

        option_values = []

        for ov in variant_option_values_map.get(v.id, []):
            all_option_values.append(ov.option_value)
            option_values.append(
                {
                    "option_name": ov.option_name,
                    "option_value": ov.option_value,
                }
            )

        variant_docs.append(
            {
                "id": v.id,
                "shopify_variant_id": v.shopify_variant_id,
                "title": v.title,
                "sku": v.sku,
                "price": float(v.price) if v.price else None,
                "inventory_quantity": v.inventory_quantity,
                "option_values": option_values,
            }
        )

    # ---------------- helpers ----------------
    def join(items):
        return " ".join([i for i in items if i])

    search_text = join(
        [
            product.title,
            product.vendor,
            product.product_type,
            product.body_html,
            join(all_skus),
            join(all_option_values),
        ]
    )

    embedding = generate_embedding(search_text)

    return {
        "id": product.id,
        "store_id": store.id,
        "shopify_product_id": product.shopify_product_id,
        "title": product.title,
        "vendor": product.vendor,
        "product_type": product.product_type,
        "handle": product.handle,
        "body_html": product.body_html,
        "status": product.status,
        "tags": product.tags or [],
        "search_text": search_text,
        "min_price": min(prices) if prices else 0,
        "max_price": max(prices) if prices else 0,
        "total_inventory": total_inventory,
        "in_stock": total_inventory > 0,
        "all_skus": all_skus,
        "all_option_values": all_option_values,
        "collections": [
            {"id": c.id, "title": c.title, "handle": c.handle} for c in collections
        ],
        "images": [{"url": i.image_url, "alt_text": i.alt_text} for i in images],
        "options": [{"name": o.name, "position": o.position} for o in options],
        "variants": variant_docs,
        "suggest": {
            "input": list(
                set(
                    [
                        product.title,
                        product.vendor,
                        *all_skus,
                        *all_option_values,
                    ]
                )
            )
        },
        "embedding": embedding,
        "embedding_model": "all-mpnet-base-v2",
        "popularity_score": 0,
        "purchase_count": 0,
    }


def upsert_product_document(es, index: str, document: Dict[str, Any]):
    return es.update(
        index=index,
        id=document["id"],
        doc=document,
        doc_as_upsert=True,
        refresh=False,
    )


# =========================================================
# FULL SHOPIFY -> DB + ELASTICSEARCH SYNC
# =========================================================


def sync_shopify_to_elasticsearch(
    session: Session,
    store: Store,
    shopify_session,
    batch_size: int = 50,
):
    print(store.shop_domain, store.access_token)
    products = fetch_shopify_products(
        shop=shopify_session.shop,
        access_token=shopify_session.access_token,
        first=batch_size,
    )

    print(f"Total products fetched: {len(products)}")

    success_count = 0
    failed_count = 0

    for node in products:
        try:
            # =============================================
            # DATABASE SYNC
            # =============================================

            sync_product_to_database(
                session=session,
                store=store,
                node=node,
            )

            # =============================================
            # ELASTICSEARCH DOCUMENT
            # =============================================

            data = transform_shopify_product(node)

            doc = build_product_document(
                product=data["product"],
                variants=data["variants"],
                images=data["images"],
                options=data["options"],
                collections=data["collections"],
                variant_option_values_map=data["variant_option_values_map"],
                store=store,
            )

            # =============================================
            # ELASTICSEARCH UPSERT
            # =============================================

            upsert_product_document(
                es=es,
                index=INDEX_ALIAS,
                document=doc,
            )

            success_count += 1

        except Exception as e:
            failed_count += 1

            print(f"Failed product: {node.get('title')} | Error: {str(e)}")

    session.commit()

    print("===================================")
    print(f"Total Products : {len(products)}")
    print(f"Success        : {success_count}")
    print(f"Failed         : {failed_count}")
    print("===================================")
