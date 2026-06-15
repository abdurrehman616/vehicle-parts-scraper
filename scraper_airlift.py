"""
Airlift scraper — uses Playwright to render the Next.js/BigCommerce site
and extracts the first 40 products from the shop page + air-springs sub-category.

Products are at /shop/{SKU} and their cards contain:
  - <p> with title text (uppercase class)
  - <p class="...text-alc-red-base"> with "PN {SKU}"
  - <p class="...font-forza..."> with "$x.xx"
"""

import asyncio
import re
from playwright.async_api import async_playwright


BASE_URL = "https://www.airliftcompany.com"

PAGES_TO_SCRAPE = [
    "/shop/",
    "/shop/by-category/air-springs/",  # replacement parts & extra SKUs
]


def _parse_card(anchor) -> dict | None:
    """Extract product data from a single <a> product card element."""
    href = anchor.get_attribute("href") or ""
    sku_match = re.search(r"/shop/([\w-]+)$", href)
    if not sku_match:
        return None
    sku = sku_match.group(1)

    inner = anchor.inner_text()
    lines = [ln.strip() for ln in inner.splitlines() if ln.strip()]

    title = ""
    price = ""
    for line in lines:
        if line.startswith("PN "):
            continue  # skip the part-number label row
        if re.match(r"^\$[\d,]+", line):
            price = line.replace("\xa0", "").strip()
        elif not title:
            title = line

    # Strip trailing " - {SKU}" that Airlift appends to many titles
    title = re.sub(rf"\s*-\s*{re.escape(sku)}\s*$", "", title).strip()

    return {"sku": sku, "title": title, "price": price, "source": "Airlift"}


async def scrape_airlift(limit: int = 40) -> list[dict]:
    products = []
    seen_skus: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        for path in PAGES_TO_SCRAPE:
            if len(products) >= limit:
                break

            url = BASE_URL + path
            print(f"[Airlift] Fetching {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except Exception as exc:
                print(f"  Warning: {exc}")
                continue

            anchors = await page.locator("a[href^='/shop/']").all()
            print(f"  Found {len(anchors)} product anchors")

            for anchor in anchors:
                href = await anchor.get_attribute("href") or ""
                sku_match = re.search(r"/shop/([\w-]+)$", href)
                if not sku_match:
                    continue
                sku = sku_match.group(1)
                if sku in seen_skus:
                    continue

                try:
                    # Use textContent (not innerText) to get proper-case text
                    # unaffected by CSS text-transform:uppercase
                    raw = await anchor.evaluate("el => el.textContent")
                except Exception:
                    continue

                raw = raw.replace("\n", " ").replace("\xa0", " ").strip()

                # Title = everything up to "PN " marker
                pn_idx = raw.find("PN ")
                if pn_idx > 0:
                    title_raw = raw[:pn_idx].strip()
                    after_pn  = raw[pn_idx:]
                else:
                    title_raw = raw
                    after_pn  = ""

                # Price = first "$x.xx" in the remainder
                price_m = re.search(r"\$([\d,]+\.?\d*)", after_pn or raw)
                price   = ("$" + price_m.group(1)) if price_m else ""

                # Strip trailing " - {SKU}" suffix Airlift appends to many titles
                title = re.sub(rf"\s*-\s*{re.escape(sku)}\s*$", "", title_raw).strip()

                if not title:
                    continue

                seen_skus.add(sku)
                products.append(
                    {"sku": sku, "title": title, "price": price, "source": "Airlift"}
                )
                if len(products) >= limit:
                    break

        await browser.close()

    print(f"[Airlift] Collected {len(products)} products")
    return products[:limit]


if __name__ == "__main__":
    import json

    data = asyncio.run(scrape_airlift())
    for p in data:
        print(p)
    print(f"\nTotal: {len(data)}")
