"""
Timbren scraper — uses Shopify's public products JSON API.

Timbren is a standard Shopify store. The endpoint:
  /collections/all/products.json?limit=40
returns up to 40 products in a single call with no authentication needed.

Each product's first variant holds the canonical SKU and price.
"""

import requests

PRODUCTS_URL = "https://timbren.com/collections/all/products.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape_timbren(limit: int = 40) -> list[dict]:
    products = []
    page = 1

    while len(products) < limit:
        resp = requests.get(
            PRODUCTS_URL,
            params={"limit": min(limit, 250), "page": page},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("products", [])

        if not data:
            break

        for item in data:
            variant = item["variants"][0] if item.get("variants") else {}
            raw_price = variant.get("price", "")
            price = f"${float(raw_price):.2f}" if raw_price else ""

            products.append(
                {
                    "sku": variant.get("sku", ""),
                    "title": item.get("title", ""),
                    "price": price,
                    "source": "Timbren",
                }
            )
            if len(products) >= limit:
                break

        page += 1

    print(f"[Timbren] Collected {len(products)} products")
    return products[:limit]


if __name__ == "__main__":
    data = scrape_timbren()
    for p in data:
        print(p)
    print(f"\nTotal: {len(data)}")
