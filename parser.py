"""
Title parser — breaks product titles into structured vehicle/fitment fields.

Handles two distinct title styles:
  • Airlift  — product-centric: "LoadLifter 5000 Air Spring Kit", "WirelessAir"
  • Timbren  — fitment-centric: "1998-2004 Nissan Frontier Desert Runner SES Kit"
              or capacity-centric: "2000 lb Axle-Less Trailer Suspension"

Output fields (all strings, empty when not applicable):
  year_start, year_end, make, model, submodel,
  product_family, product_type, capacity, position, modifier
"""

import re


# ---------------------------------------------------------------------------
# Airlift product family names (longest match wins)
# ---------------------------------------------------------------------------
AIRLIFT_FAMILIES = [
    "LoadLifter 7500 XL Ultimate",
    "LoadLifter 5000 Ultimate",
    "LoadLifter 5000",
    "LoadLifter ProSeries",
    "RideControl",
    "Air Lift 1000HD",
    "Air Lift 1000",
    "WirelessAir",
    "WirelessONE",
    "LoadController II",
    "LoadController Dual",
    "LoadController Single",
    "LoadController",
    "Towtal View LaneGuard Pro",
    "Towtal View LaneGuard",
    "Towtal View",
]

AIRLIFT_PRODUCT_TYPES = [
    "Air Spring Kit",
    "Air Spring Spacer",
    "Air Spring Cradle",
    "Air Down Gauge",
    "Power Adapter",
    "Clamp Adapter",
    "Portable Compressor",
    "Compressor",
    "Camera",
]

TRAILER_KEYWORDS = [
    "Axle-Less", "Silent Ride", "Tandem Axle", "Single Axle",
    "Trailer Suspension", "Brake Hub", "Electric Brake",
    "wheel end kit", "axle wheel",
]

# Ordered product-type suffix patterns for Timbren vehicle titles.
# Matched left-to-right; first match wins.
_TIMBREN_PRODUCT_SUFFIX_PATTERNS = [
    (re.compile(r"Timbren\s+SES\b.*$", re.I),        "Timbren SES Kit"),
    (re.compile(r"SES\s+Coil\s+Enhancer\s+Kit.*$", re.I), "SES Coil Enhancer Kit"),
    (re.compile(r"SES\s+Kit.*$", re.I),               "SES Kit"),
    (re.compile(r"\bSES\b.*$", re.I),                 "Timbren SES Kit"),
    (re.compile(r"Suspension\s+Enhancement\s+System.*$", re.I), "Timbren SES Kit"),
    (re.compile(r"Truck\s+Camper\s+Kit.*$", re.I),    "Truck Camper Kit"),
    (re.compile(r"Rear\s+Kit.*$", re.I),              "Rear Kit"),
    (re.compile(r"Front\s+Kit.*$", re.I),             "Front Kit"),
]

_YEAR_RANGE = re.compile(
    r"(?P<y1>(?:19|20)?\d{2})"          # start year (may be 2-digit: "22")
    r"\s*[-–]|\bto\b\s*"                # separator  – but we rewrite below
    r"(?P<y2>(?:(?:19|20)\d{2})|[Pp]resent)",
)

# Re-implement year range as a single, unambiguous pattern
_YEAR_RANGE = re.compile(
    r"(?P<y1>(?:19|20)?\d{2})"
    r"(?:\s*[-–]\s*|\s+to\s+)"
    r"(?P<y2>(?:(?:19|20)\d{2})|[Pp]resent)",
    re.IGNORECASE,
)

_POSITION = re.compile(r"\b(Front|Rear|Truck\s+Camper)\b", re.IGNORECASE)
_CAP_LB    = re.compile(r"([\d,]+)\s*lb\b", re.IGNORECASE)
_CAP_TONNE = re.compile(r"(\d+(?:\.\d+)?)\s*[Tt]onne\b")
_MOD_W     = re.compile(r"\bw/\s*(.+)", re.IGNORECASE)
_SPREAD    = re.compile(r"with\s+(\d+)\s+inch\s+Axle\s+Spread", re.IGNORECASE)
_SPACER    = re.compile(r"(\d+)-?in\.?\s+(Level|Angled)\s+Universal\s+Air\s+Spring\s+Spacer", re.IGNORECASE)


def _expand_year(raw: str) -> str:
    return ("20" + raw) if len(raw) == 2 else raw


def _strip_inline_sku(title: str, sku: str) -> str:
    """Remove SKU references embedded in the title text."""
    # "SKU# NDR001" anywhere (with optional preceding dash)
    title = re.sub(rf"\s*[-–]?\s*SKU#?\s+{re.escape(sku)}\b", "", title, flags=re.IGNORECASE)
    # bare trailing dash + SKU at very end: "- NDR001"
    title = re.sub(rf"\s*[-–]\s*{re.escape(sku)}\s*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def _empty_record() -> dict:
    return {
        "year_start": "", "year_end": "", "make": "", "model": "",
        "submodel": "", "product_family": "", "product_type": "",
        "capacity": "", "position": "", "modifier": "",
    }


# ---------------------------------------------------------------------------
# Airlift
# ---------------------------------------------------------------------------

def _parse_airlift(title: str, sku: str) -> dict:
    r = _empty_record()
    t = _strip_inline_sku(title, sku)

    # Product family (longest match)
    for fam in AIRLIFT_FAMILIES:
        if fam.lower() in t.lower():
            r["product_family"] = fam
            break

    # Product type
    for pt in AIRLIFT_PRODUCT_TYPES:
        if pt.lower() in t.lower():
            r["product_type"] = pt
            break

    # Air spring spacer special case
    m = _SPACER.search(t)
    if m:
        r["capacity"] = m.group(1) + "-in"
        r["modifier"] = m.group(2).title()
        r["product_type"] = "Air Spring Spacer"

    # LoadController sub-description in parens
    if r["product_family"].startswith("LoadController"):
        paren = re.search(r"\(([^)]+)\)", t)
        if paren:
            r["submodel"] = paren.group(1).strip()

    # Compressor system modifiers
    if "EZ Mount" in t:
        r["modifier"] = "Tank Plus EZ Mount" if re.search(r"tank.*plus", t, re.I) else "EZ Mount"
    elif re.search(r"tank.*plus", t, re.I):
        r["modifier"] = "Tank Plus"

    # App Only variant
    if "App Only" in t:
        r["submodel"] = (r["submodel"] + " App Only").strip()

    return r


# ---------------------------------------------------------------------------
# Timbren
# ---------------------------------------------------------------------------

def _parse_timbren(title: str, sku: str) -> dict:
    r = _empty_record()
    t = _strip_inline_sku(title, sku)

    # ----- Trailer / capacity products ----------------------------------
    is_trailer = any(kw.lower() in t.lower() for kw in TRAILER_KEYWORDS)

    cap_lb    = _CAP_LB.search(t)
    cap_tonne = _CAP_TONNE.search(t)

    if cap_lb:
        r["capacity"] = cap_lb.group(1).replace(",", "") + " lb"
    elif cap_tonne:
        r["capacity"] = cap_tonne.group(1) + " Tonne"

    if is_trailer:
        # Start from after the capacity token
        if cap_lb:
            rest = t[cap_lb.end():].strip()
        elif cap_tonne:
            rest = t[cap_tonne.end():].strip()
        else:
            rest = t

        # Strip leading "HD" tag (baked into capacity field)
        if re.match(r"^HD\b", rest, re.I):
            rest = rest[2:].strip()
            r["submodel"] = "HD"

        # "with N inch Axle Spread"
        m = _SPREAD.search(rest)
        if m:
            r["modifier"] = m.group(1) + '" Axle Spread'
            rest = rest[: m.start()].strip()

        # "w/ 4\" Drop & Long Spindles"
        m = _MOD_W.search(rest)
        if m:
            r["modifier"] = m.group(1).strip()
            rest = rest[: m.start()].strip()

        r["product_type"] = rest.strip(" -,")

        pos_m = _POSITION.search(t)
        if pos_m:
            r["position"] = pos_m.group(1).replace("  ", " ").title()

        return r

    # ----- Vehicle-specific products ------------------------------------
    yr_m = _YEAR_RANGE.search(t)
    if not yr_m:
        return r

    r["year_start"] = _expand_year(yr_m.group("y1"))
    y2 = yr_m.group("y2")
    r["year_end"] = "Present" if y2.lower() == "present" else _expand_year(y2)

    # Full text after the primary year range
    full_remainder = t[yr_m.end():].strip().lstrip("-–,. ").strip()

    # Step 1: strip trailing "- (Position) Kit" suffix from the full remainder
    #   e.g. "… Timbren SES … - Rear Kit" or "… - Truck Camper Kit"
    _KIT_SUFFIX = re.compile(
        r"\s*[-–]\s*(Front|Rear|Truck\s+Camper)\s+Kit\s*$", re.IGNORECASE
    )
    ks = _KIT_SUFFIX.search(full_remainder)
    if ks:
        r["position"] = ks.group(1).strip().title()
        full_remainder = full_remainder[: ks.start()].strip()

    # Step 2: detect and strip product-type suffix from full remainder
    #   (must happen BEFORE "&" split so multi-vehicle titles like
    #   "Tundra & Tacoma … SES Kit" still yield a product type)
    for pat, product_type in _TIMBREN_PRODUCT_SUFFIX_PATTERNS:
        m = pat.search(full_remainder)
        if m:
            r["product_type"] = product_type
            full_remainder = full_remainder[: m.start()].strip()
            break

    # Step 3: first vehicle segment (before any "&" joining multiple vehicles)
    vehicle_part = re.split(r"\s*[&]\s*", full_remainder)[0].strip()

    # Remove secondary year ranges (e.g. "'24-Present" in the Tacoma title)
    vehicle_part = re.sub(
        r"'?(?:(?:19|20)?\d{2})\s*[-–]\s*(?:(?:19|20)\d{2}|[Pp]resent)\s*",
        "", vehicle_part, flags=re.I
    ).strip()

    # Strip trailing punctuation noise
    vehicle_part = re.sub(r"\s*[-–]\s*$", "", vehicle_part).strip()
    # Remove stray "Kit" words
    vehicle_part = re.sub(r"\bKit\b", "", vehicle_part, flags=re.I)
    # Remove Timbren brand
    vehicle_part = re.sub(r"\bTimbren\b", "", vehicle_part, flags=re.I)
    # Collapse whitespace
    vehicle_part = re.sub(r"\s{2,}", " ", vehicle_part).strip(" -,")

    tokens = vehicle_part.split()
    if tokens:
        r["make"]  = tokens[0].strip(",.;:")
        r["model"] = tokens[1].strip(",.;:") if len(tokens) > 1 else ""
        if len(tokens) > 2:
            r["submodel"] = " ".join(tokens[2:]).strip(",.;:")

    # Fallback position from remaining remainder if not yet set
    if not r["position"]:
        pos_m = _POSITION.search(full_remainder)
        if pos_m:
            r["position"] = pos_m.group(0).strip().title()

    # If we know the position but not the product type, infer "{Position} Kit"
    if r["position"] and not r["product_type"]:
        r["product_type"] = r["position"] + " Kit"

    return r


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_product(record: dict) -> dict:
    """
    Accept a raw product dict {sku, title, price, source}.
    Return the same dict extended with parsed fitment/product fields.

    Any parsing exception leaves affected fields empty — the pipeline
    always receives a complete, safe row.
    """
    result = dict(record)
    parsed = _empty_record()

    try:
        src   = record.get("source", "")
        title = record.get("title", "")
        sku   = record.get("sku",   "")

        if src == "Airlift":
            parsed = _parse_airlift(title, sku)
        elif src == "Timbren":
            parsed = _parse_timbren(title, sku)
    except Exception as exc:
        print(f"  [parser] ERROR on '{record.get('title', '')}': {exc}")

    result.update(parsed)
    return result


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    samples = [
        # Airlift
        {"sku": "57541", "title": "LoadLifter 7500 XL Ultimate Air Spring Kit", "price": "$800.99", "source": "Airlift"},
        {"sku": "25980EZ", "title": "WirelessONE with EZ Mount", "price": "$713.99", "source": "Airlift"},
        {"sku": "74100EZ", "title": "WirelessAir Tank plus EZ Mount", "price": "$1363.99", "source": "Airlift"},
        {"sku": "25592", "title": "LoadController II (Single Path, Standard Duty)", "price": "$336.99", "source": "Airlift"},
        {"sku": "52440", "title": "4-in. Level Universal Air Spring Spacer", "price": "$113.99", "source": "Airlift"},
        {"sku": "16188", "title": "Digital Portable Compressor", "price": "", "source": "Airlift"},
        {"sku": "25342", "title": "Towtal View LaneGuard Pro", "price": "$866.99", "source": "Airlift"},
        # Timbren vehicle-specific
        {"sku": "NDR001", "title": "1998-2004 Nissan Frontier Desert Runner Timbren SES Suspension Enhancement System SKU# NDR001", "price": "$316.90", "source": "Timbren"},
        {"sku": "IVR110HD", "title": "1999-2014 IVECO 50C18 - Rear Kit", "price": "$584.30", "source": "Timbren"},
        {"sku": "GMRH2", "title": "2003-2009 GMC Hummer H2 Timbren SES Suspension Enhancement System SKU# GMRH2 - Rear Kit", "price": "$316.90", "source": "Timbren"},
        {"sku": "TORTTNDR", "title": "22-Present Toyota Tundra & '24-Present Toyota Tacoma Timbren SES Suspension Enhancement System - Truck Camper Kit", "price": "$468.32", "source": "Timbren"},
        {"sku": "CE10G40P", "title": "2013-present Subaru Crosstrek & 2022-present Hyundai Santa Cruz SES Coil Enhancer Kit", "price": "$244.34", "source": "Timbren"},
        {"sku": "JRGD", "title": "2020 to Present Jeep JT Gladiator Timbren SES Suspension Enhancement System - Rear Kit", "price": "$316.90", "source": "Timbren"},
        # Timbren trailer
        {"sku": "ASR1THDS01", "title": "1 Tonne HD Axle-Less Trailer Suspension", "price": "$1027.03", "source": "Timbren"},
        {"sku": "ASR1THDS05", "title": '1 Tonne HD Axle-Less Trailer Suspension w/ 4" Drop', "price": "$1091.66", "source": "Timbren"},
        {"sku": "SR10KT02", "title": "10,000 lb Tandem Axle Silent Ride Trailer Suspension", "price": "$2044.86", "source": "Timbren"},
        {"sku": "SR14KT01", "title": "14000 lb Tandem Axle Silent Ride Trailer Suspension with 33 inch Axle Spread", "price": "$2164.40", "source": "Timbren"},
    ]

    for s in samples:
        p = parse_product(s)
        print(f"\nTitle   : {s['title'][:80]}")
        print(f"  years : {p['year_start']}-{p['year_end']}")
        print(f"  make/model/sub : {p['make']!r} / {p['model']!r} / {p['submodel']!r}")
        print(f"  pos   : {p['position']!r}")
        print(f"  family: {p['product_family']!r}   type: {p['product_type']!r}")
        print(f"  cap   : {p['capacity']!r}   mod: {p['modifier']!r}")
