"""
AI analyzer - calls DeepSeek API for deep analysis and suggestions.
"""
import json
import urllib.request
import urllib.error
import http.client
import os
import time
import ssl

# DeepSeek API config
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def analyze_with_ai(diagnosis, competitor_data=None, product_keyword=""):
    """
    Send diagnosis + competitor data to DeepSeek for 7-dimension analysis.

    Args:
        diagnosis: dict from rule_engine.diagnose()
        competitor_data: list of competitor product dicts (optional)
        product_keyword: the seller's product keyword

    Returns:
        dict with:
            - analysis: str (markdown formatted AI analysis)
            - suggestions: list of str (actionable suggestions)
            - error: None or error message
    """
    stats = diagnosis.get("stats", {})
    alerts = diagnosis.get("alerts", [])
    performance = diagnosis.get("performance", {})

    # Build prompt
    prompt_parts = []
    prompt_parts.append("You are an Amazon advertising optimization expert.")
    prompt_parts.append("Analyze the following Amazon Sponsored Products ad data and provide actionable suggestions.\n")

    prompt_parts.append("## Overall Performance")
    prompt_parts.append(f"- Total Spend: ${stats.get('total_spend', 0):.2f}")
    prompt_parts.append(f"- Total Sales: ${stats.get('total_sales', 0):.2f}")
    prompt_parts.append(f"- Overall ACOS: {stats.get('overall_acos', 0):.1f}%")
    prompt_parts.append(f"- Total Clicks: {stats.get('total_clicks', 0)}")
    prompt_parts.append(f"- Total Orders: {stats.get('total_orders', 0)}")
    prompt_parts.append(f"- Wasted Spend (zero-order keywords): ${stats.get('wasted_spend', 0):.2f} ({stats.get('wasted_pct', 0):.1f}%)")
    prompt_parts.append(f"- Keywords: {stats.get('good_count', 0)} good, {stats.get('warning_count', 0)} warning, {stats.get('critical_count', 0)} critical\n")

    # Top problem keywords
    prompt_parts.append("## Top Problem Keywords")
    for alert in alerts[:10]:
        prompt_parts.append(
            f"- [{alert['level'].upper()}] {alert['message']} | Suggested: {alert['suggestion']}"
        )

    # Good keywords
    good_kws = performance.get("good", [])[:5]
    if good_kws:
        prompt_parts.append("\n## Top Performing Keywords")
        for kw in good_kws:
            prompt_parts.append(
                f"- {kw.get('keyword','')}: spend ${kw.get('spend',0):.2f}, "
                f"orders {kw.get('orders',0)}, ACOS {kw.get('acos',0):.1f}%"
            )

    # Competitor data
    if competitor_data and len(competitor_data) > 0:
        prompt_parts.append(f"\n## Competitor Data ({len(competitor_data)} products)")
        # aggregate competitor stats
        prices = [c.get("price", 0) for c in competitor_data if c.get("price")]
        ratings = [c.get("rating", 0) for c in competitor_data if c.get("rating")]
        reviews = [c.get("reviews", 0) for c in competitor_data if c.get("reviews")]

        if prices:
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            prompt_parts.append(f"- Price range: ${min_price:.2f} - ${max_price:.2f} (avg ${avg_price:.2f})")
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            prompt_parts.append(f"- Average rating: {avg_rating:.1f}")
        if reviews:
            avg_reviews = sum(reviews) / len(reviews)
            prompt_parts.append(f"- Average reviews: {avg_reviews:.0f}")

        # top 5 competitors by reviews
        sorted_comp = sorted(competitor_data, key=lambda x: x.get("reviews", 0), reverse=True)[:5]
        prompt_parts.append("- Top 5 competitors by review count:")
        for c in sorted_comp:
            prompt_parts.append(
                f"  - {c.get('title','')[:60]}... | ${c.get('price',0):.2f} | "
                f"{c.get('rating',0)} stars | {c.get('reviews',0)} reviews"
            )

    prompt_parts.append("\n## Please provide:")
    prompt_parts.append("1. Overall diagnosis (what's working, what's broken)")
    prompt_parts.append("2. Top 3 most urgent actions (ranked by money-saving potential)")
    prompt_parts.append("3. Bid strategy recommendations (which keywords to increase/decrease/pause)")
    prompt_parts.append("4. Competitor insights (how does the seller compare on price/rating/reviews)")
    prompt_parts.append("5. Listing optimization suggestions")
    prompt_parts.append("6. Budget reallocation plan (move money from bad keywords to good ones)")
    prompt_parts.append("7. 7-day action plan with specific steps")
    prompt_parts.append("\nWrite in Chinese (Simplified). Use markdown formatting.")

    prompt = "\n".join(prompt_parts)

    # Build API payload
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert Amazon advertising consultant. Provide specific, actionable advice based on data. Always respond in Chinese."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 3000,
        "temperature": 0.7,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }

    # Call DeepSeek API (with retry)
    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = _call_deepseek_api(payload, headers)
            analysis_text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not analysis_text:
                return {"analysis": "AI returned empty response.", "suggestions": [], "error": "empty_response"}

            return {
                "analysis": analysis_text,
                "suggestions": extract_suggestions(analysis_text),
                "error": None,
            }
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(2)
                continue

    return {
        "analysis": _fallback_analysis(diagnosis, competitor_data),
        "suggestions": [],
        "error": f"DeepSeek API unavailable: {str(last_error)}",
    }


def _call_deepseek_api(payload, headers):
    """Call DeepSeek API with proper SSL handling and chunked read."""
    data = json.dumps(payload).encode("utf-8")

    # Use http.client for more reliable chunked reading
    parsed_url = urllib.request.urlparse(DEEPSEEK_API_URL)
    conn = http.client.HTTPSConnection(
        parsed_url.hostname,
        parsed_url.port or 443,
        timeout=90,
        context=ssl.create_default_context(),
    )

    conn.request("POST", parsed_url.path, body=data, headers=headers)
    resp = conn.getresponse()

    # Read in chunks to avoid IncompleteRead
    body = b""
    while True:
        chunk = resp.read(8192)
        if not chunk:
            break
        body += chunk

    conn.close()

    if resp.status != 200:
        raise urllib.error.HTTPError(DEEPSEEK_API_URL, resp.status, resp.reason, {}, None)

    return json.loads(body.decode("utf-8"))


def extract_suggestions(text):
    """Extract bullet-point suggestions from AI response."""
    suggestions = []
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("- ") or line.startswith("* ") or line.startswith("\u2022 "):
            suggestions.append(line[2:])
        elif len(line) > 10 and line[0].isdigit() and "." in line[:4]:
            suggestions.append(line)
    return suggestions


def _fallback_analysis(diagnosis, competitor_data=None):
    """Generate a basic analysis without AI when DeepSeek is unavailable."""
    stats = diagnosis.get("stats", {})
    alerts = diagnosis.get("alerts", [])
    perf = diagnosis.get("performance", {})

    lines = []
    lines.append("## \u57fa\u7840\u8bca\u65ad\u62a5\u544a\uff08AI \u6682\u4e0d\u53ef\u7528\uff0c\u4ee5\u4e0b\u4e3a\u89c4\u5219\u5f15\u64ce\u5206\u6790\uff09\n")

    lines.append("### \u6574\u4f53\u8868\u73b0")
    lines.append(f"- \u603b\u82b1\u8d39: ${stats.get('total_spend', 0):.2f}")
    lines.append(f"- \u603b\u9500\u552e\u989d: ${stats.get('total_sales', 0):.2f}")
    lines.append(f"- \u6574\u4f53 ACOS: {stats.get('overall_acos', 0):.1f}%")
    if stats.get("overall_acos", 0) > 100:
        lines.append("- \u26a0\ufe0f ACOS \u8d85\u8fc7 100%\uff0c\u5e7f\u544a\u652f\u51fa\u5927\u4e8e\u6536\u5165\uff0c\u7d27\u6025\u9700\u8981\u4f18\u5316")
    elif stats.get("overall_acos", 0) > 60:
        lines.append("- \u26a0\ufe0f ACOS \u504f\u9ad8\uff0c\u5efa\u8bae\u964d\u4f4e\u51fa\u4ef7")
    lines.append(f"- \u6d6a\u8d39\u82b1\u8d39: ${stats.get('wasted_spend', 0):.2f} ({stats.get('wasted_pct', 0):.1f}%)")
    lines.append("")

    if alerts:
        lines.append("### \u7d27\u6025\u5904\u7406\u9879")
        for a in alerts[:5]:
            lines.append(f"- [{a['level'].upper()}] {a['message']}")
            lines.append(f"  \u5efa\u8bae: {a['suggestion']}")
        lines.append("")

    good = perf.get("good", [])
    if good:
        lines.append("### \u8868\u73b0\u4f18\u79c0\u7684\u5173\u952e\u8bcd\uff08\u5efa\u8bae\u589e\u52a0\u9884\u7b97\uff09")
        for kw in good[:5]:
            lines.append(f"- {kw.get('keyword', '')}: ACOS {kw.get('acos', 0):.1f}%, {kw.get('orders', 0)} \u8ba2\u5355")
        lines.append("")

    if competitor_data:
        prices = [c.get("price", 0) for c in competitor_data if c.get("price")]
        ratings = [c.get("rating", 0) for c in competitor_data if c.get("rating")]
        if prices:
            avg_p = sum(prices) / len(prices)
            lines.append("### \u7ade\u54c1\u5bf9\u6bd4")
            lines.append(f"- \u7ade\u54c1\u5e73\u5747\u4ef7\u683c: ${avg_p:.2f}")
            lines.append(f"- \u4ef7\u683c\u8303\u56f4: ${min(prices):.2f} ~ ${max(prices):.2f}")
            if ratings:
                lines.append(f"- \u7ade\u54c1\u5e73\u5747\u8bc4\u5206: {sum(ratings)/len(ratings):.1f}")

    lines.append("\n---")
    lines.append("\u6ce8: DeepSeek AI \u6682\u4e0d\u53ef\u7528\uff0c\u4ee5\u4e0a\u4e3a\u89c4\u5219\u5f15\u64ce\u81ea\u52a8\u5206\u6790\u7ed3\u679c\u3002\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002")

    return "\n".join(lines)
