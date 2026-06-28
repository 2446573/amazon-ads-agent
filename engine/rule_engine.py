"""
Rule engine - automated diagnosis of Amazon Ads data.
Handles the 80% of decisions that don't need AI.
"""
import json


def diagnose(data):
    """
    Analyze parsed keyword data and produce diagnostic findings.

    Args:
        data: dict from csv_parser.parse_csv()

    Returns:
        dict with:
            - alerts: list of {level, category, keyword, message, suggestion}
            - performance: {good, warning, critical} keyword lists
            - stats: summary metrics for display
    """
    keywords = data.get("keywords", [])
    summary = data.get("summary", {})

    alerts = []
    good_kw = []
    warning_kw = []
    critical_kw = []

    total_spend = summary.get("total_spend", 0)
    total_sales = summary.get("total_sales", 0)
    total_clicks = summary.get("total_clicks", 0)
    total_orders = summary.get("total_orders", 0)

    for kw in keywords:
        name = kw.get("keyword", "")
        spend = kw.get("spend", 0)
        clicks = kw.get("clicks", 0)
        orders = kw.get("orders", 0)
        sales = kw.get("sales", 0)
        acos = kw.get("acos", 0)
        cpc = kw.get("cpc", 0)
        cvr = kw.get("cvr", 0)

        # Rule 1: Spending money, zero orders
        if spend >= 10 and orders == 0:
            alerts.append({
                "level": "critical",
                "category": "wasted_spend",
                "keyword": name,
                "message": f"'{name}' spent ${spend:.2f} with 0 orders",
                "suggestion": f"Pause or reduce bid. CPC is ${cpc:.2f}, but conversion rate is 0%.",
                "spend": spend,
                "clicks": clicks,
                "orders": orders,
                "sales": sales,
                "acos": acos,
            })
            critical_kw.append(kw)

        # Rule 2: ACOS too high (> 100%)
        elif acos > 100 and orders > 0:
            alerts.append({
                "level": "critical",
                "category": "high_acos",
                "keyword": name,
                "message": f"'{name}' ACOS = {acos:.1f}% (spend ${spend:.2f} / sales ${sales:.2f})",
                "suggestion": f"Reduce bid by 30-50%, or pause if no improvement in 7 days.",
                "spend": spend,
                "clicks": clicks,
                "orders": orders,
                "sales": sales,
                "acos": acos,
            })
            critical_kw.append(kw)

        # Rule 3: ACOS elevated (60% - 100%)
        elif 60 < acos <= 100 and orders > 0:
            alerts.append({
                "level": "warning",
                "category": "elevated_acos",
                "keyword": name,
                "message": f"'{name}' ACOS = {acos:.1f}%, above 60% threshold",
                "suggestion": f"Lower bid by 10-20%, check search term relevance.",
                "spend": spend,
                "clicks": clicks,
                "orders": orders,
                "sales": sales,
                "acos": acos,
            })
            warning_kw.append(kw)

        # Rule 4: High clicks but low conversion
        elif clicks >= 50 and cvr < 2:
            alerts.append({
                "level": "warning",
                "category": "low_conversion",
                "keyword": name,
                "message": f"'{name}' got {clicks} clicks but only {orders} orders (CVR={cvr:.1f}%)",
                "suggestion": f"Check listing quality (images, A+ content, reviews). Issue may be listing, not ads.",
                "spend": spend,
                "clicks": clicks,
                "orders": orders,
                "sales": sales,
                "acos": acos,
            })
            warning_kw.append(kw)

        # Rule 5: Good performers
        elif orders > 0 and 0 < acos < 50:
            good_kw.append(kw)

        # Rule 6: Low spend, inconclusive
        else:
            if spend < 5:
                pass  # too little data
            else:
                warning_kw.append(kw)

    # Sort alerts by spend (highest first)
    alerts.sort(key=lambda x: x.get("spend", 0), reverse=True)

    # Calculate waste metrics
    wasted_spend = sum(a["spend"] for a in alerts if a["category"] == "wasted_spend")
    high_acos_spend = sum(a["spend"] for a in alerts if a["category"] == "high_acos")

    stats = {
        "total_spend": total_spend,
        "total_sales": total_sales,
        "total_clicks": total_clicks,
        "total_orders": total_orders,
        "overall_acos": round(total_spend / total_sales * 100, 2) if total_sales > 0 else 0,
        "wasted_spend": round(wasted_spend, 2),
        "wasted_pct": round(wasted_spend / total_spend * 100, 1) if total_spend > 0 else 0,
        "high_acos_spend": round(high_acos_spend, 2),
        "good_count": len(good_kw),
        "warning_count": len(warning_kw),
        "critical_count": len(critical_kw),
        "total_keywords": len(keywords),
    }

    return {
        "alerts": alerts,
        "performance": {
            "good": good_kw,
            "warning": warning_kw,
            "critical": critical_kw,
        },
        "stats": stats,
    }
