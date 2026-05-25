from typing import Optional, List
from elasticsearch import Elasticsearch
from fastapi import APIRouter, Depends, Query

from app.services.product_index import generate_embedding
from app.helpers import get_es, get_store_id_by_shop
from app.auth import ShopifySession, verify_shopify_token

router = APIRouter()


# ==========================================
# AUTOCOMPLETE ROUTER
# ==========================================
@router.get("/product/autocomplete/")
def get_product_auto_suggestion(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=20),
    es: Elasticsearch = Depends(get_es),
    session: ShopifySession = Depends(verify_shopify_token),
):
    print(session, session.shop, session.user_id)
    store_id = get_store_id_by_shop(shop_domain=session.shop)
    """
    Fast autocomplete with:
    - search_as_you_type
    - fuzzy matching
    - duplicate removal
    - popularity sorting
    """

    q = q.strip()

    if not q:
        return {"suggestions": []}

    query = {
        "size": limit * 3,  # fetch extra because we dedupe later
        "_source": [
            "title",
            "vendor",
            "handle",
        ],
        "query": {
            "bool": {
                # ====================================
                # # MULTI TENANT FILTER
                # # ====================================
                "filter": [{"term": {"store_id": store_id}}],
                "should": [
                    # ====================================
                    # BEST autocomplete field
                    # ====================================
                    {
                        "multi_match": {
                            "query": q,
                            "type": "bool_prefix",
                            "fields": [
                                "title.suggest",
                                "title.suggest._2gram",
                                "title.suggest._3gram",
                            ],
                            "boost": 10,
                        }
                    },
                    # ====================================
                    # TYPO TOLERANCE
                    # ====================================
                    {
                        "match": {
                            "title": {
                                "query": q,
                                "fuzziness": "AUTO",
                                "boost": 5,
                            }
                        }
                    },
                    # ====================================
                    # EXACT PREFIX
                    # ====================================
                    {
                        "prefix": {
                            "title.keyword": {
                                "value": q.lower(),
                                "boost": 20,
                            }
                        }
                    },
                    # ====================================
                    # SEARCH TEXT
                    # ====================================
                    {
                        "match": {
                            "search_text": {
                                "query": q,
                                "boost": 3,
                            }
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        },
        # ====================================
        # SORTING
        # ====================================
        "sort": [
            {"popularity_score": {"order": "desc"}},
            {"purchase_count": {"order": "desc"}},
            {"view_count": {"order": "desc"}},
            "_score",
        ],
    }

    response = es.search(
        index="products",
        body=query,
    )

    hits = response["hits"]["hits"]

    # ==========================================
    # REMOVE DUPLICATES
    # ==========================================

    seen = set()
    suggestions = []

    for hit in hits:
        source = hit["_source"]

        title = source.get("title")

        if not title:
            continue

        normalized = title.strip().lower()

        if normalized in seen:
            continue

        seen.add(normalized)

        suggestions.append(title)

        if len(suggestions) >= limit:
            break

    return {
        "query": q,
        "count": len(suggestions),
        "suggestions": suggestions,
    }


# =========================================================
# AMAZON-LIKE PRODUCT SEARCH
# =========================================================
@router.get("/products/list/")
def get_products(
    # =====================================================
    # SEARCH
    # =====================================================
    q: Optional[str] = Query(None),
    # =====================================================
    # FILTERS
    # =====================================================
    vendor: Optional[List[str]] = Query(None),
    product_type: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    in_stock: Optional[bool] = Query(None),
    # =====================================================
    # VARIANT FILTERS
    # =====================================================
    colors: Optional[List[str]] = Query(None),
    sizes: Optional[List[str]] = Query(None),
    # =====================================================
    # SORT
    # =====================================================
    sort_by: str = Query(
        "relevance",
        description="relevance | price_asc | price_desc | newest | popular",
    ),
    # =====================================================
    # PAGINATION
    # =====================================================
    page: int = Query(1, ge=1),
    size: int = Query(20, le=100),
    # =====================================================
    # VECTOR SEARCH
    # =====================================================
    es: Elasticsearch = Depends(get_es),
    session: ShopifySession = Depends(verify_shopify_token),
):
    store_id = get_store_id_by_shop(shop_domain=session.shop)
    offset = (page - 1) * size

    # =====================================================
    # MAIN SEARCH QUERY
    # =====================================================
    must_queries = []

    if q:
        must_queries.append(
            {
                "bool": {
                    # ====================================
                    # # MULTI TENANT FILTER
                    # # ====================================
                    "filter": [{"term": {"store_id": store_id}}],
                    "should": [
                        {
                            "multi_match": {
                                "query": q,
                                "fields": [
                                    "title^8",
                                    "title.suggest^10",
                                    "vendor^2",
                                    "search_text^4",
                                    "body_html",
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO",
                            }
                        },
                        {
                            "multi_match": {
                                "query": q,
                                "type": "bool_prefix",
                                "fields": [
                                    "title.suggest",
                                    "title.suggest._2gram",
                                    "title.suggest._3gram",
                                ],
                                "boost": 15,
                            }
                        },
                        {
                            "term": {
                                "all_skus": {
                                    "value": q,
                                    "boost": 50,
                                }
                            }
                        },
                        {
                            "term": {
                                "all_barcodes": {
                                    "value": q,
                                    "boost": 50,
                                }
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    # =====================================================
    # FILTER BUILDERS
    # =====================================================
    all_filters = {
        "vendor": (vendor, lambda values: {"terms": {"vendor.keyword": values}}),
        "product_type": (
            product_type,
            lambda values: {"terms": {"product_type": values}},
        ),
        "tags": (tags, lambda values: {"terms": {"tags": values}}),
        "colors": (
            colors,
            lambda values: {
                "nested": {
                    "path": "variants.option_values",
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "term": {
                                        "variants.option_values.option_name": "Color"
                                    }
                                },
                                {
                                    "terms": {
                                        "variants.option_values.option_value": values
                                    }
                                },
                            ]
                        }
                    },
                }
            },
        ),
        "sizes": (
            sizes,
            lambda values: {
                "nested": {
                    "path": "variants.option_values",
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "term": {
                                        "variants.option_values.option_name": "Size"
                                    }
                                },
                                {
                                    "terms": {
                                        "variants.option_values.option_value": values
                                    }
                                },
                            ]
                        }
                    },
                }
            },
        ),
    }

    active_filters = {}

    for key, (values, builder) in all_filters.items():
        if values:
            active_filters[key] = builder(values)

    # =====================================================
    # PRICE FILTER
    # =====================================================
    if min_price is not None or max_price is not None:
        price_filter = {"range": {"min_price": {}}}
        if min_price is not None:
            price_filter["range"]["min_price"]["gte"] = min_price
        if max_price is not None:
            price_filter["range"]["min_price"]["lte"] = max_price

        active_filters["price"] = price_filter

    # =====================================================
    # STOCK FILTER
    # =====================================================
    if in_stock is not None:
        active_filters["in_stock"] = {"term": {"in_stock": in_stock}}

    # =====================================================
    # BASE QUERY
    # =====================================================
    query = {
        "from": offset,
        "size": size,
        "track_total_hits": True,
        "_source": {"excludes": ["embedding"]},
        "query": {
            "bool": {"must": (must_queries if must_queries else [{"match_all": {}}])}
        },
    }

    if active_filters:
        query["post_filter"] = {"bool": {"must": list(active_filters.values())}}

    # =====================================================
    # FACET FILTER BUILDER (UNCHANGED)
    # =====================================================
    def build_facet_filter(exclude_key: str):
        return {
            "bool": {
                "must": [
                    value for key, value in active_filters.items() if key != exclude_key
                ]
            }
        }

    # =====================================================
    # FACETS (UNCHANGED STRUCTURE)
    # =====================================================
    query["aggs"] = {
        "vendors": {
            "filter": build_facet_filter("vendor"),
            "aggs": {"buckets": {"terms": {"field": "vendor.keyword", "size": 50}}},
        },
        "product_types": {
            "filter": build_facet_filter("product_type"),
            "aggs": {"buckets": {"terms": {"field": "product_type", "size": 50}}},
        },
        "tags": {
            "filter": build_facet_filter("tags"),
            "aggs": {"buckets": {"terms": {"field": "tags", "size": 100}}},
        },
        "colors": {
            "filter": build_facet_filter("colors"),
            "aggs": {
                "filter_colors": {
                    "nested": {"path": "variants.option_values"},
                    "aggs": {
                        "values": {
                            "filter": {
                                "term": {"variants.option_values.option_name": "Color"}
                            },
                            "aggs": {
                                "buckets": {
                                    "terms": {
                                        "field": "variants.option_values.option_value",
                                        "size": 100,
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
        "sizes": {
            "filter": build_facet_filter("sizes"),
            "aggs": {
                "filter_sizes": {
                    "nested": {"path": "variants.option_values"},
                    "aggs": {
                        "values": {
                            "filter": {
                                "term": {"variants.option_values.option_name": "Size"}
                            },
                            "aggs": {
                                "buckets": {
                                    "terms": {
                                        "field": "variants.option_values.option_value",
                                        "size": 100,
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
        "price_stats": {
            "filter": build_facet_filter("price"),
            "aggs": {"stats": {"stats": {"field": "min_price"}}},
        },
    }

    # =====================================================
    # SORTING (UNCHANGED)
    # =====================================================
    if sort_by == "price_asc":
        query["sort"] = [{"min_price": {"order": "asc"}}]
    elif sort_by == "price_desc":
        query["sort"] = [{"min_price": {"order": "desc"}}]
    elif sort_by == "popular":
        query["sort"] = [
            {"popularity_score": {"order": "desc"}},
            {"purchase_count": {"order": "desc"}},
            {"view_count": {"order": "desc"}},
        ]
    elif sort_by == "newest":
        query["sort"] = [{"id": {"order": "desc"}}]
    elif sort_by == "vendor_asc":
        query["sort"] = [{"vendor.keyword": {"order": "asc"}}]

    elif sort_by == "vendor_desc":
        query["sort"] = [{"vendor.keyword": {"order": "desc"}}]
    elif sort_by == "title_asc":
        query["sort"] = [{"title.keyword": {"order": "asc"}}]

    elif sort_by == "title_desc":
        query["sort"] = [{"title.keyword": {"order": "desc"}}]

    elif sort_by == "product_type_asc":
        query["sort"] = [
            {
                "product_type": {
                    "order": "asc",
                }
            }
        ]

    elif sort_by == "product_type_desc":
        query["sort"] = [
            {
                "product_type": {
                    "order": "desc",
                }
            }
        ]
    else:
        query["sort"] = ["_score", {"popularity_score": {"order": "desc"}}]

    # =====================================================
    # EXECUTE FIRST SEARCH (TEXT SEARCH)
    # =====================================================
    response = es.search(index="products", body=query)

    total_hits = response["hits"]["total"]["value"]

    # =====================================================
    # ✅ ONLY IF 0 RESULTS → USE VECTOR SEARCH
    # =====================================================
    if total_hits == 0 and q:
        embedding = generate_embedding(
            q
        )  # <-- your smallest sentence-transformer model

        query["query"] = {
            "bool": {
                "must": [{"match_all": {}}],
            }
        }

        query["knn"] = {
            "field": "embedding",
            "query_vector": embedding,
            "k": size,
            "num_candidates": 100,
        }

        response = es.search(index="products", body=query)

    # =====================================================
    # FORMAT RESULTS
    # =====================================================
    hits = response["hits"]["hits"]

    products = []
    for hit in hits:
        source = hit["_source"]
        source["_score"] = hit["_score"]
        products.append(source)

    return {
        "query": q,
        "pagination": {
            "page": page,
            "size": size,
            "total": response["hits"]["total"]["value"],
            "total_pages": (response["hits"]["total"]["value"] + size - 1) // size,
        },
        "products": products,
        "facets": response.get("aggregations", {}),
    }
