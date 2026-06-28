# Amazon Ads Optimization Agent

> Open-source Amazon PPC optimization tool for small sellers. Upload your ad report, get AI-powered suggestions. Free alternative to Helium 10 / Ad Badger.

## Features

- **Ad Report Diagnosis** - Upload Amazon Search Term Report CSV, automatically identify wasted spend, high ACOS keywords, and low-conversion terms
- **Competitor Analysis** - Multi-keyword search via Apify, fetch real-time competitor pricing, ratings, and review data from Amazon
- **AI Deep Analysis** - DeepSeek AI analyzes 7 dimensions: keyword intent, match type, bid strategy, competitor insights, listing optimization, budget reallocation, 7-day action plan
- **Rule Engine** - Python-based if-else logic handles 80% of deterministic diagnoses instantly
- **Report Export** - Download analysis as text file for sharing

## Quick Start

### Prerequisites

- Python 3.10+
- DeepSeek API Key ([get one here](https://platform.deepseek.com/))
- Apify API Token ([get one here](https://console.apify.com/)) - optional, for live competitor data

### Installation

```bash
git clone https://github.com/2446573/amazon-ads-agent.git
cd amazon-ads-agent
pip install -r requirements.txt
```

### Configuration

1. Copy `.env.example` to `.env`
2. Fill in your API keys:

```
DEEPSEEK_API_KEY=your_key_here
APIFY_API_TOKEN=your_token_here
FLASK_SECRET_KEY=any_random_string
CONTACT_EMAIL=your@email.com
CONTACT_PHONE=your_phone
CONTACT_WECHAT=your_wechat_id
```

### Run

```bash
python app.py
```

Open http://localhost:5000 in your browser.

## How It Works

1. **Upload** - Seller uploads Amazon Search Term Report CSV (or uses demo mode)
2. **Diagnose** - Rule engine scans keywords: identifies wasted spend, high ACOS, low conversion
3. **Competitors** - Apify scrapes Amazon search results for competitor data (multi-keyword, ASIN dedup)
4. **AI Analysis** - DeepSeek AI generates 7-dimension analysis with actionable suggestions
5. **Report** - View interactive report, download as text file

## Multi-Keyword Scraping

- 1 keyword: scrapes top 50 results
- 2-5 keywords: scrapes top 20 results per keyword, deduplicates by ASIN
- Estimated cost: ~$0.20-$0.40 per analysis (Apify free tier: $5/month)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML + CSS + Vanilla JS |
| Backend | Python Flask |
| AI | DeepSeek API |
| Data Scraping | Apify Amazon Scraper |
| Storage | Local JSON files |

## Project Structure

```
website/
  app.py              # Flask application, routes
  requirements.txt    # Python dependencies
  Procfile            # For Render.com deployment
  .env.example        # Environment variable template
  engine/
    csv_parser.py     # Parse Amazon ad report CSV
    rule_engine.py    # Rule-based diagnosis
    ai_analyzer.py    # DeepSeek AI integration
    apify_scraper.py  # Apify Amazon scraper
  templates/
    index.html        # Homepage
    upload.html       # Data upload page
    report.html       # Analysis report
    history.html      # Past reports
    contact.html      # Contact page
  static/css/
    style.css         # All styles
  data/
    uploads/          # Uploaded CSV files
    reports/          # Generated reports (JSON)
    contacts/         # Contact form submissions
```

## Deployment

### Render.com (recommended)

1. Push to GitHub
2. Connect repo to Render.com
3. Set environment variables (DEEPSEEK_API_KEY, APIFY_API_TOKEN, etc.)
4. Deploy - Render auto-detects Procfile

### Local

```bash
python app.py
# Open http://localhost:5000
```

## Contributing

Pull requests welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](LICENSE) - free to use, modify, and distribute.

## Contact

- Email: 13924543277@163.com
- WeChat: wxid_8gmhbvvsaecp22
- GitHub: https://github.com/2446573
