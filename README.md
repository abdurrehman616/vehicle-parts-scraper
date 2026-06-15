# Data Scraper Pipeline

A mini data scraping pipeline that collects, parses, and structures product data from **Air Lift Company** and **Timbren** into a clean Excel spreadsheet.

---

## What It Does

| Step | Script | Description |
|------|--------|-------------|
| Scrape | `scraper_airlift.py` | Renders the Next.js/BigCommerce Airlift site with Playwright and extracts product cards |
| Scrape | `scraper_timbren.py` | Calls Timbren's public Shopify JSON API (`/collections/all/products.json`) |
| Parse | `parser.py` | Breaks raw product title strings into structured fitment fields |
| Output | `pipeline.py` | Orchestrates all steps and writes a styled Excel file |

**Output:** `products.xlsx` — 3 sheets, 80 records (40 Airlift + 40 Timbren), 14 columns each.

---

## Output Columns

| Column | Description |
|--------|-------------|
| Source | `Airlift` or `Timbren` |
| SKU | Part number |
| Product Title | Raw title from the website |
| Price | Listed price (e.g. `$316.90`) |
| Year Start | First model year (e.g. `1998`) |
| Year End | Last model year or `Present` |
| Make | Vehicle manufacturer (e.g. `Nissan`) |
| Model | Vehicle model (e.g. `Frontier`) |
| Sub-Model | Trim/sub-variant (e.g. `Desert Runner`) |
| Product Family | Airlift product line (e.g. `LoadLifter 5000`) |
| Product Type | Kit category (e.g. `SES Kit`, `Air Spring Kit`) |
| Capacity | Load rating for trailer products (e.g. `10000 lb`) |
| Position | Front / Rear / Truck Camper |
| Modifier | Special configuration (e.g. `EZ Mount`, `33" Axle Spread`) |

---

## Requirements

- **Python 3.11** (Playwright is installed under `python3.11`)
- pip packages: `playwright`, `requests`, `pandas`, `openpyxl`

### Install dependencies

```bash
pip3.11 install playwright requests pandas openpyxl
python3.11 -m playwright install chromium
```

---

## How to Run

### Run the full pipeline (recommended)

```bash
python3.11 pipeline.py
```

This runs all three steps in sequence and produces `products.xlsx`.

**Expected output:**

```
============================================================
STEP 1  Scraping product data
============================================================
[Airlift] Fetching https://www.airliftcompany.com/shop/
  Found 67 product anchors
[Airlift] Fetching https://www.airliftcompany.com/shop/by-category/air-springs/
  Found 17 product anchors
[Airlift] Collected 40 products
[Timbren] Collected 40 products

============================================================
STEP 2  Parsing product titles
============================================================
  Airlift  parsed : 40 records
  Timbren  parsed : 40 records

============================================================
STEP 3  Writing Excel output
============================================================
  Written → /path/to/products.xlsx
  Airlift  : 40 rows
  Timbren  : 40 rows
  All      : 80 rows

Done.
```

---

### Run individual scripts

```bash
# Scrape Airlift only
python3.11 scraper_airlift.py

# Scrape Timbren only
python3.11 scraper_timbren.py

# Test the title parser on sample data
python3.11 parser.py
```

---

## Project Structure

```
data-scraper/
├── scraper_airlift.py   # Playwright scraper for Air Lift Company
├── scraper_timbren.py   # Shopify API scraper for Timbren
├── parser.py            # Regex-based title → structured fields parser
├── pipeline.py          # Orchestrator + Excel output
├── products.xlsx        # Final output (generated on run)
└── README.md            # This file
```

---

## Exception Handling

The pipeline handles three categories of failures gracefully:

**Website format changes** — the Airlift scraper uses URL-pattern matching (`/shop/{SKU}`) and `textContent` extraction rather than brittle CSS selectors, so minor layout changes don't break the scraper. The Timbren scraper targets the Shopify JSON API which has a stable, versioned schema. If a field (price, PN label) is missing from a product card, the scraper logs the anomaly and skips that field rather than crashing.

**Parsing failures** — every `parse_product()` call is wrapped in a `try/except`. If a title doesn't match any known pattern (e.g. a new product type with unexpected formatting), the parsed fields are left empty while the raw SKU, title, and price are still preserved in the output row — no record is ever dropped entirely.

**Network / timeout errors** — the Playwright pages use `wait_until="networkidle"` with a 45-second timeout per page. If a page fails to load, the scraper logs a warning and moves on to the next URL in `PAGES_TO_SCRAPE`, so a single-page failure does not abort the entire run. The Timbren scraper similarly catches HTTP errors via `raise_for_status()` and stops pagination cleanly if the API returns an empty response.
