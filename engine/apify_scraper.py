"""
Apify scraper - fetch competitor data from Amazon via Apify.
Supports multi-keyword search with ASIN deduplication.
Falls back to local data if API call fails.
"""
import json
import os
import urllib.request
import urllib.error
import time

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
APIFY_ACTOR_ID = "n1Zg5k1A5Rkw0S5nN"  # Amazon Scraper
APIFY_API_BASE = "https://api.apify.com/v2"

# Pricing: $0.004 per result + $0.001 per run start
COST_PER_RESULT = 0.004
COST_PER_RUN = 0.001


def search_competitors(keywords, use_apify=True):
    """
    Search Amazon for products matching keywords via Apify.
    Supports multi-keyword search with ASIN deduplication.

    Args:
        keywords: list of search keywords (max 5), e.g. ["dog toys", "dog chew toys"]
        use_apify: if True, call Apify API; if False, use local fallback data

    Returns:
        dict with:
            - products: list of {asin, title, brand, price, rating, reviews, url, source_keyword}
            - source: "apify" or "local_fallback"
            - error: None or error message
            - keywords_used: list of keywords actually used
            - total_crawled: int (before dedup)
            - deduplicated: int (after dedup)
            - estimated_cost: float (USD)
    """
    # Normalize keywords to list
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    keywords = list(dict.fromkeys(keywords))[:5]  # dedupe, max 5

    if not keywords:
        return {"products": [], "source": "none", "error": "No keywords provided",
                "keywords_used": [], "total_crawled": 0, "deduplicated": 0, "estimated_cost": 0}

    # Determine per-keyword result count
    if len(keywords) == 1:
        per_keyword = 50
    else:
        per_keyword = 20

    estimated_cost = _estimate_cost(keywords, per_keyword)

    # Try Apify if requested
    if use_apify:
        all_products = []
        for kw in keywords:
            try:
                products = _call_apify(kw, per_keyword)
                for p in products:
                    p["source_keyword"] = kw
                all_products.extend(products)
            except Exception as e:
                print(f"Apify call failed for '{kw}': {e}")

        if all_products:
            total_crawled = len(all_products)
            unique_products = _deduplicate_by_asin(all_products)
            return {
                "products": unique_products,
                "source": "apify",
                "error": None,
                "keywords_used": keywords,
                "total_crawled": total_crawled,
                "deduplicated": len(unique_products),
                "estimated_cost": estimated_cost,
            }

    # Fallback to local data
    local = _load_local_data("")
    if local:
        # Simulate multi-keyword by slicing different portions
        result_products = []
        for i, kw in enumerate(keywords):
            start = (i * per_keyword) % len(local)
            end = min(start + per_keyword, len(local))
            for p in local[start:end]:
                p_copy = dict(p)
                p_copy["source_keyword"] = kw
                result_products.append(p_copy)

        total_crawled = len(result_products)
        unique_products = _deduplicate_by_asin(result_products)
        return {
            "products": unique_products,
            "source": "local_fallback",
            "error": None,
            "keywords_used": keywords,
            "total_crawled": total_crawled,
            "deduplicated": len(unique_products),
            "estimated_cost": 0,
        }

    return {"products": [], "source": "none", "error": "No competitor data available",
            "keywords_used": keywords, "total_crawled": 0, "deduplicated": 0, "estimated_cost": 0}


def _call_apify(keyword, max_results):
    """Call Apify Amazon Scraper actor."""
    run_payload = {
        "searchQueries": [keyword],
        "maxResults": max_results,
        "countryCode": "US",
    }

    start_url = f"{APIFY_API_BASE}/acts/{APIFY_ACTOR_ID}/runs?token={APIFY_TOKEN}&waitForFinish=120"

    req = urllib.request.Request(
        start_url,
        data=json.dumps(run_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=130) as resp:
        run_data = json.loads(resp.read().decode("utf-8"))

    dataset_id = run_data.get("defaultDatasetId")
    if not dataset_id:
        raise Exception("No dataset returned from Apify")

    # Fetch dataset items
    dataset_url = f"{APIFY_API_BASE}/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json"
    with urllib.request.urlopen(dataset_url, timeout=30) as resp:
        items = json.loads(resp.read().decode("utf-8"))

    # Normalize items
    products = []
    for item in items[:max_results]:
        product = {
            "asin": item.get("asin", ""),
            "title": item.get("title", "")[:80],
            "brand": item.get("brand", item.get("sellerName", "")),
            "price": _parse_price(item),
            "price_display": item.get("price", ""),
            "rating": _parse_rating(item),
            "reviews": _parse_reviews(item),
            "availability": item.get("availability", "In Stock"),
            "url": item.get("url", f"https://www.amazon.com/dp/{item.get('asin','')}"),
        }
        if product["asin"]:
            products.append(product)

    return products


def _deduplicate_by_asin(products):
    """Remove duplicate products by ASIN, keeping first occurrence."""
    seen_asins = set()
    unique = []
    for p in products:
        asin = p.get("asin", "")
        if asin and asin not in seen_asins:
            seen_asins.add(asin)
            unique.append(p)
        elif not asin:
            unique.append(p)  # keep items without ASIN
    return unique


def _estimate_cost(keywords, per_keyword):
    """Estimate Apify cost in USD."""
    total_results = len(keywords) * per_keyword
    total_runs = len(keywords)
    return round(total_results * COST_PER_RESULT + total_runs * COST_PER_RUN, 3)


def _parse_price(item):
    """Extract numeric price from various Apify response formats."""
    price = item.get("price")
    if price is None:
        price = item.get("priceValue")
    if price is None:
        return 0.0
    if isinstance(price, (int, float)):
        return float(price)
    s = str(price).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_rating(item):
    rating = item.get("rating")
    if rating is None:
        rating = item.get("stars")
    if rating is None:
        return 0.0
    if isinstance(rating, (int, float)):
        return float(rating)
    s = str(rating).replace("out of 5 stars", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_reviews(item):
    reviews = item.get("reviewsCount")
    if reviews is None:
        reviews = item.get("reviews")
    if reviews is None:
        return 0
    if isinstance(reviews, (int, float)):
        return int(reviews)
    s = str(reviews).replace(",", "").strip()
    try:
        return int(s)
    except ValueError:
        return 0


def _load_local_data(keyword):
    """Load local competitor data as fallback."""
    local_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "competitor_data_real.json"),
        os.path.join(os.path.dirname(__file__), "..", "data", "competitor_data_real.json"),
    ]

    for path in local_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
            except Exception:
                pass

    return []
