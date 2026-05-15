# =========================================================
# FULL PRODUCT FETCH WITH PAGINATION
# =========================================================

import requests
from typing import List, Dict, Any

SHOPIFY_GRAPHQL_URL = "https://{shop}/admin/api/2024-10/graphql.json"


def fetch_shopify_products(
    shop: str,
    access_token: str,
    first: int = 50,
) -> List[Dict[str, Any]]:
    url = SHOPIFY_GRAPHQL_URL.format(shop=shop)

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    all_products = []

    has_next_page = True
    cursor = None

    query = """
    query GetProducts($first: Int!, $cursor: String) {
      products(first: $first, after: $cursor) {

        pageInfo {
          hasNextPage
        }

        edges {
          cursor

          node {
            id
            title
            handle
            vendor
            productType
            descriptionHtml
            status
            tags

            options {
              id
              name
              position
            }

            images(first: 20) {
              edges {
                node {
                  id
                  url
                  altText
                  width
                  height
                }
              }
            }

            variants(first: 100) {
              edges {
                node {
                  id
                  title
                  sku
                  barcode
                  price
                  compareAtPrice
                  inventoryQuantity
                  position
                  taxable

                  selectedOptions {
                    name
                    value
                  }
                }
              }
            }

            collections(first: 20) {
              edges {
                node {
                  id
                  title
                  handle
                }
              }
            }
          }
        }
      }
    }
    """

    while has_next_page:
        response = requests.post(
            url,
            json={
                "query": query,
                "variables": {
                    "first": first,
                    "cursor": cursor,
                },
            },
            headers=headers,
            timeout=60,
        )

        data = response.json()

        if "errors" in data:
            raise Exception(data["errors"])

        products_data = data["data"]["products"]

        edges = products_data["edges"]

        for edge in edges:
            all_products.append(edge["node"])

        has_next_page = products_data["pageInfo"]["hasNextPage"]

        # next cursor
        if edges:
            cursor = edges[-1]["cursor"]

        print(f"Fetched {len(all_products)} products...")

    return all_products
