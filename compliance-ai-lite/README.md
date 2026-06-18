# ComplianceAI Lite

> AI-powered RBI regulatory monitoring for Indian fintech companies.
> Instantly view AI-generated summaries of the latest RBI circulars — no manual reading required.

---

## What It Does

Compliance officers at NBFCs, payment companies, and digital lenders spend 30–90 minutes every morning
manually reading RBI circulars. ComplianceAI Lite eliminates that.

Open one page. See structured summaries of the latest circulars in under 2 minutes.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Python 3.12 |
| Frontend | Jinja2 + Tailwind CSS |
| AI | Google Gemini 1.5 Flash |
| Scraping | BeautifulSoup4 + requests |
| PDF | pdfplumber |
| Hosting | Render |

---

## Project Structure

```
compliance-ai-lite/
├── app.py                          # FastAPI entry point
├── config.py                       # Pydantic Settings (env vars)
├── requirements.txt
├── render.yaml                     # Render deployment config
├── .env.example                    # Environment variable template
│
├── src/
│   ├── routes/
│   │   └── circulars.py            # GET /, GET /api/circulars, POST /api/refresh
│   ├── services/
│   │   └── circular_service.py     # Pipeline orchestrator
│   ├── scraper/
│   │   └── rbi_scraper.py          # RBI website scraper
│   ├── parsers/
│   │   └── pdf_parser.py           # PDF downloader + text extractor
│   ├── ai/
│   │   └── gemini_client.py        # Gemini AI integration
│   ├── schemas/
│   │   └── circular.py             # Pydantic data models
│   └── utils/
│       ├── cache.py                # In-memory TTL cache
│       └── logger.py               # Structured logging
│
├── templates/
│   └── index.html                  # Jinja2 HTML template
├── static/
│   └── css/
│       └── styles.css              # Custom CSS
└── tests/
    ├── test_scraper.py
    ├── test_pdf_parser.py
    ├── test_gemini_client.py
    └── test_circular_service.py
```

---

## Local Development

### Prerequisites

- Python 3.12+
- A Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/compliance-ai-lite.git
cd compliance-ai-lite

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY to your actual key

# 5. Run the development server
uvicorn app:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Homepage with circular cards |
| `GET` | `/api/circulars` | JSON list of circular summaries |
| `POST` | `/api/refresh` | Force-refresh (bypasses cache) |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI (development only) |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | ✅ Yes | — | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-1.5-flash` | Gemini model identifier |
| `APP_ENV` | No | `development` | `development` or `production` |
| `RBI_CIRCULAR_LIMIT` | No | `5` | Number of circulars to fetch |
| `CACHE_TTL_MINUTES` | No | `30` | Cache duration in minutes |
| `PDF_MAX_TOKENS` | No | `8000` | Max characters sent to Gemini |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

---

## Running Tests

```bash
pytest --cov=src --cov-report=term-missing
```

Tests are fully offline — all external calls (RBI, Gemini) are mocked.

---

## Deployment (Render)

1. Push to GitHub.
2. Create a new **Web Service** on [Render](https://render.com) and connect your repository.
3. Render will detect `render.yaml` automatically.
4. Set `GOOGLE_API_KEY` in the Render dashboard under **Environment**.
5. Deploy.

---

## Architecture

```
Browser → FastAPI → CircularService → [ RBIScraper | PDFParser | GeminiClient ]
                        ↕
                   TTL Cache (30 min)
```

Caching ensures the Gemini API is called at most once per TTL window regardless of traffic.

---

## Scope

**MVP includes:** RBI scraper · PDF extraction · Gemini summaries · Web UI · Render deployment

**Out of scope:** Login · Database · Email · SEBI · IRDAI · Search · Filters · Notifications

---

## License

MIT — see [LICENSE](LICENSE).
