"""
Amazon Ads Optimization Agent - Flask Application
Run: python app.py
Open: http://localhost:5000
"""
import json
import os
import uuid
from datetime import datetime

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path)
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, redirect, url_for

from engine.csv_parser import parse_csv, get_sample_data
from engine.rule_engine import diagnose
from engine.ai_analyzer import analyze_with_ai
from engine.apify_scraper import search_competitors

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
REPORT_DIR = os.path.join(DATA_DIR, "reports")
CONTACT_DIR = os.path.join(DATA_DIR, "contacts")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(CONTACT_DIR, exist_ok=True)

# Contact info (displayed in footer and contact page)
CONTACT_INFO = {
    "email": os.environ.get("CONTACT_EMAIL", "13924543277@163.com"),
    "phone": os.environ.get("CONTACT_PHONE", "13924543277"),
    "wechat": os.environ.get("CONTACT_WECHAT", "wxid_8gmhbvvsaecp22"),
    "github": "https://github.com/2446573",
}


@app.context_processor
def inject_contact_info():
    """Make contact info available in all templates."""
    return {"contact": CONTACT_INFO}


@app.route("/")
def index():
    """Homepage"""
    return render_template("index.html")


@app.route("/upload")
def upload_page():
    """Upload data page"""
    return render_template("upload.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Main analysis endpoint.
    Accepts:
        - csv_file: uploaded CSV file (optional if demo mode)
        - demo_mode: "true" to use sample data
        - product_keyword: seller's product keyword(s), comma-separated
        - use_apify: "true" to fetch live competitor data
    Returns:
        - JSON with report_id, or error
    """
    demo_mode = request.form.get("demo_mode") == "true"
    product_keyword_raw = request.form.get("product_keyword", "").strip()
    use_apify = request.form.get("use_apify") == "true"

    # Parse comma-separated keywords into list (max 5)
    keywords = [k.strip() for k in product_keyword_raw.split(",") if k.strip()]
    keywords = list(dict.fromkeys(keywords))[:5]  # dedupe, max 5

    if not keywords:
        keywords = ["dog toys"]  # default fallback

    # Step 1: Get CSV data
    csv_content = None
    if demo_mode:
        csv_content = get_sample_data()
    else:
        file = request.files.get("csv_file")
        if not file or file.filename == "":
            return jsonify({"error": "Please upload a CSV file or use demo mode"}), 400
        csv_content = file.read().decode("utf-8-sig")
        safe_name = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.csv"
        filepath = os.path.join(UPLOAD_DIR, safe_name)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(csv_content)

    # Step 2: Parse CSV
    parsed = parse_csv(csv_content)
    if parsed["parse_error"]:
        return jsonify({"error": parsed["parse_error"]}), 400

    # Step 3: Rule engine diagnosis
    diagnosis = diagnose(parsed)

    # Step 4: Get competitor data (multi-keyword)
    competitor_result = {"products": [], "source": "skipped", "error": None,
                         "keywords_used": [], "total_crawled": 0, "deduplicated": 0,
                         "estimated_cost": 0}

    if use_apify:
        competitor_result = search_competitors(keywords, use_apify=True)
    else:
        # use local data as default
        competitor_result = search_competitors(keywords, use_apify=False)

    # Step 5: AI analysis
    ai_result = analyze_with_ai(
        diagnosis,
        competitor_data=competitor_result.get("products", []),
        product_keyword=", ".join(keywords),
    )

    # Step 6: Build and save report
    report_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    report = {
        "report_id": report_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "product_keyword": ", ".join(keywords),
        "keywords_list": keywords,
        "demo_mode": demo_mode,
        "summary": parsed["summary"],
        "diagnosis": diagnosis,
        "competitors": {
            "source": competitor_result.get("source", "none"),
            "count": len(competitor_result.get("products", [])),
            "products": competitor_result.get("products", [])[:50],
            "keywords_used": competitor_result.get("keywords_used", []),
            "total_crawled": competitor_result.get("total_crawled", 0),
            "deduplicated": competitor_result.get("deduplicated", 0),
            "estimated_cost": competitor_result.get("estimated_cost", 0),
        },
        "ai_analysis": ai_result.get("analysis", ""),
        "ai_suggestions": ai_result.get("suggestions", []),
        "ai_error": ai_result.get("error"),
    }

    # Save report to file
    report_path = os.path.join(REPORT_DIR, f"report_{report_id}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return jsonify({"report_id": report_id, "redirect": f"/report/{report_id}"})


@app.route("/report/<report_id>")
def report_page(report_id):
    """Display report page"""
    report_path = os.path.join(REPORT_DIR, f"report_{report_id}.json")
    if not os.path.exists(report_path):
        return render_template("error.html", message="Report not found"), 404

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    return render_template("report.html", report=report)


@app.route("/api/report/<report_id>")
def api_get_report(report_id):
    """API endpoint to get report data as JSON"""
    report_path = os.path.join(REPORT_DIR, f"report_{report_id}.json")
    if not os.path.exists(report_path):
        return jsonify({"error": "Report not found"}), 404

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    return jsonify(report)


@app.route("/history")
def history_page():
    """History page - list all past reports"""
    reports = []
    if os.path.exists(REPORT_DIR):
        for fname in sorted(os.listdir(REPORT_DIR), reverse=True):
            if fname.startswith("report_") and fname.endswith(".json"):
                filepath = os.path.join(REPORT_DIR, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    reports.append({
                        "report_id": data.get("report_id", ""),
                        "created_at": data.get("created_at", ""),
                        "product_keyword": data.get("product_keyword", ""),
                        "demo_mode": data.get("demo_mode", False),
                        "keyword_count": data.get("summary", {}).get("keyword_count", 0),
                        "total_spend": data.get("summary", {}).get("total_spend", 0),
                        "overall_acos": data.get("diagnosis", {}).get("stats", {}).get("overall_acos", 0),
                        "critical_count": data.get("diagnosis", {}).get("stats", {}).get("critical_count", 0),
                    })
                except Exception:
                    pass

    return render_template("history.html", reports=reports)


@app.route("/contact", methods=["GET", "POST"])
def contact_page():
    """Contact page - display info and collect messages"""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not email or not message:
            return jsonify({"error": "Email and message are required"}), 400

        contact_data = {
            "name": name,
            "email": email,
            "message": message,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        filename = f"contact_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.json"
        filepath = os.path.join(CONTACT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(contact_data, f, ensure_ascii=False, indent=2)

        return jsonify({"success": True, "message": "Message sent! We will contact you soon."})

    return render_template("contact.html")


@app.route("/download/<report_id>")
def download_report(report_id):
    """Download report as text file"""
    report_path = os.path.join(REPORT_DIR, f"report_{report_id}.json")
    if not os.path.exists(report_path):
        return "Report not found", 404

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    lines = []
    lines.append("=" * 60)
    lines.append("  Amazon Ads Optimization Report")
    lines.append("=" * 60)
    lines.append(f"Date: {report.get('created_at', '')}")
    lines.append(f"Product: {report.get('product_keyword', '')}")
    lines.append(f"Mode: {'Demo' if report.get('demo_mode') else 'Real Data'}")
    lines.append("")

    summary = report.get("summary", {})
    lines.append("--- Overall Performance ---")
    lines.append(f"Total Spend: ${summary.get('total_spend', 0):.2f}")
    lines.append(f"Total Sales: ${summary.get('total_sales', 0):.2f}")
    lines.append(f"Overall ACOS: {report.get('diagnosis', {}).get('stats', {}).get('overall_acos', 0):.1f}%")
    lines.append(f"Total Clicks: {summary.get('total_clicks', 0)}")
    lines.append(f"Total Orders: {summary.get('total_orders', 0)}")
    lines.append(f"Wasted Spend: ${report.get('diagnosis', {}).get('stats', {}).get('wasted_spend', 0):.2f}")
    lines.append("")

    lines.append("--- Problem Keywords ---")
    for alert in report.get("diagnosis", {}).get("alerts", [])[:15]:
        lines.append(f"[{alert['level'].upper()}] {alert['message']}")
        lines.append(f"  -> {alert['suggestion']}")
    lines.append("")

    lines.append("--- Competitor Data ---")
    competitors = report.get("competitors", {})
    lines.append(f"Source: {competitors.get('source', 'N/A')}")
    lines.append(f"Count: {competitors.get('count', 0)}")
    lines.append(f"Keywords: {', '.join(competitors.get('keywords_used', []))}")
    lines.append(f"Crawled: {competitors.get('total_crawled', 0)} | After dedup: {competitors.get('deduplicated', 0)}")
    for p in competitors.get("products", [])[:10]:
        lines.append(f"  - {p.get('title','')[:50]} | ${p.get('price',0):.2f} | {p.get('rating',0)} stars | {p.get('reviews',0)} reviews | kw: {p.get('source_keyword','')}")
    lines.append("")

    lines.append("--- AI Analysis ---")
    lines.append(report.get("ai_analysis", "N/A"))
    lines.append("")
    lines.append("=" * 60)

    text_content = "\n".join(lines)

    from flask import Response
    return Response(
        text_content,
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename=report_{report_id}.txt"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  Amazon Ads Optimization Agent")
    print(f"  Open: http://localhost:{port}")
    print("=" * 50)

    # Try waitress (Windows compatible), fall back to Flask dev server
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=True)
