"""
CSV parser - parse Amazon Ads sponsored products search term report.
Handles various column name formats from Amazon Seller Central exports.
"""
import csv
import io
import json
from datetime import datetime


# Amazon CSV reports have various column name formats.
# We map common variations to our standard field names.
COLUMN_MAP = {
    # keyword / search term
    "Keyword": "keyword",
    "Search Term": "keyword",
    "Customer Search Term": "keyword",
    "customer_search_term": "keyword",
    # spend
    "Spend": "spend",
    "Cost": "spend",
    "spend": "spend",
    # clicks
    "Clicks": "clicks",
    "clicks": "clicks",
    # impressions
    "Impressions": "impressions",
    "impressions": "impressions",
    # orders / conversions
    "Orders": "orders",
    "Conversions": "orders",
    "7 Day Total Orders": "orders",
    "7 Day Total Orders (#)": "orders",
    "orders": "orders",
    # sales
    "Sales": "sales",
    "7 Day Total Sales": "sales",
    "7 Day Total Sales ($)": "sales",
    "sales": "sales",
    # ACOS
    "ACOS": "acos",
    "Acos": "acos",
    "acos": "acos",
    # CPC
    "CPC": "cpc",
    "cpc": "cpc",
    # CTR
    "CTR": "ctr",
    "ctr": "ctr",
    # Conversion rate
    "Conversion Rate": "cvr",
    "cvr": "cvr",
}


def normalize_column(name):
    """Map a CSV column header to our standard field name."""
    if not name:
        return None
    # strip whitespace
    clean = name.strip()
    # try direct match
    if clean in COLUMN_MAP:
        return COLUMN_MAP[clean]
    # try case-insensitive match
    for key, val in COLUMN_MAP.items():
        if key.lower() == clean.lower():
            return val
    return None


def parse_float(val):
    """Safely parse a float from various string formats."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s == "--":
        return 0.0
    # remove $ and , and %
    s = s.replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_int(val):
    """Safely parse an int."""
    f = parse_float(val)
    return int(f)


def parse_csv(content_text):
    """
    Parse Amazon Ads CSV content into a list of keyword records.

    Returns: dict with keys:
        - keywords: list of {keyword, spend, clicks, impressions, orders, sales, acos, cpc, cvr}
        - summary: {total_spend, total_clicks, total_impressions, total_orders, total_sales, avg_acos}
        - parse_error: None or error message
    """
    result = {
        "keywords": [],
        "summary": {},
        "parse_error": None,
    }

    if not content_text or not content_text.strip():
        result["parse_error"] = "CSV file is empty"
        return result

    # detect delimiter (Amazon uses comma or tab)
    first_line = content_text.split("\n")[0]
    if "\t" in first_line:
        delimiter = "\t"
    else:
        delimiter = ","

    reader = csv.DictReader(io.StringIO(content_text), delimiter=delimiter)

    # build column index mapping
    field_map = {}
    for raw_col in reader.fieldnames or []:
        std = normalize_column(raw_col)
        if std:
            field_map[raw_col] = std

    if "keyword" not in field_map.values():
        result["parse_error"] = (
            "Cannot find keyword/search term column. "
            "Please make sure this is an Amazon Sponsored Products Search Term Report."
        )
        return result

    total_spend = 0.0
    total_clicks = 0
    total_impressions = 0
    total_orders = 0
    total_sales = 0.0

    for row in reader:
        rec = {}
        for raw_col, std_name in field_map.items():
            val = row.get(raw_col, "")
            if std_name in ("spend", "sales", "acos", "cpc", "ctr", "cvr"):
                rec[std_name] = parse_float(val)
            elif std_name in ("clicks", "impressions", "orders"):
                rec[std_name] = parse_int(val)
            else:
                rec[std_name] = str(val).strip()

        # ensure all fields exist (before calculations)
        rec.setdefault("spend", 0.0)
        rec.setdefault("clicks", 0)
        rec.setdefault("impressions", 0)
        rec.setdefault("orders", 0)
        rec.setdefault("sales", 0.0)
        rec.setdefault("acos", 0.0)
        rec.setdefault("cpc", 0.0)
        rec.setdefault("cvr", 0.0)
        rec.setdefault("ctr", 0.0)

        # calculate derived fields if missing
        if rec["clicks"] > 0:
            if rec["cpc"] == 0:
                rec["cpc"] = round(rec["spend"] / rec["clicks"], 2)
            if rec["ctr"] == 0 and rec["impressions"] > 0:
                rec["ctr"] = round(rec["clicks"] / rec["impressions"] * 100, 2)
        if rec["clicks"] > 0 and rec["orders"] > 0 and rec["cvr"] == 0:
            rec["cvr"] = round(rec["orders"] / rec["clicks"] * 100, 2)
        if rec["spend"] > 0 and rec["sales"] > 0 and rec["acos"] == 0:
            rec["acos"] = round(rec["spend"] / rec["sales"] * 100, 2)

        # skip empty rows
        if not rec.get("keyword"):
            continue

        result["keywords"].append(rec)

        total_spend += rec["spend"]
        total_clicks += rec["clicks"]
        total_impressions += rec["impressions"]
        total_orders += rec["orders"]
        total_sales += rec["sales"]

    avg_acos = round(total_spend / total_sales * 100, 2) if total_sales > 0 else 0.0
    avg_cpc = round(total_spend / total_clicks, 2) if total_clicks > 0 else 0.0
    avg_cvr = round(total_orders / total_clicks * 100, 2) if total_clicks > 0 else 0.0

    result["summary"] = {
        "total_spend": round(total_spend, 2),
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "total_orders": total_orders,
        "total_sales": round(total_sales, 2),
        "avg_acos": avg_acos,
        "avg_cpc": avg_cpc,
        "avg_cvr": avg_cvr,
        "keyword_count": len(result["keywords"]),
    }

    return result


def get_sample_data():
    """Return sample Amazon Ads data for demo mode."""
    sample_csv = """Keyword,Spend,Clicks,Impressions,Orders,Sales,ACOS
dog chew toys,45.20,120,3200,3,89.97,50.2
indestructible dog toy,32.10,85,2100,1,22.99,139.7
puppy toys,18.50,60,1500,0,0,0
dog toys for large dogs,28.90,75,2800,2,47.98,60.2
interactive dog toys,15.30,40,980,1,15.99,95.7
dog rope toy,22.40,55,1700,0,0,0
squeaky dog toys,12.80,35,890,1,29.99,42.7
tough dog toys,38.60,95,2500,2,39.98,96.6
dog ball,9.20,25,600,0,0,0
dog plush toys,16.70,42,1100,1,12.99,128.5
kong dog toy,52.30,130,3500,4,119.96,43.6
dog toys aggressive chewers,41.50,100,2700,1,19.99,207.6
"""
    return sample_csv
