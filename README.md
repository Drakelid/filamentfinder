# FilamentFinder - 3D Printing Consumables Price Tracker

A complete price tracking and change logging system for 3D printing consumables (filaments and UV resins) that scrapes user-provided websites.

## Features

- **Multi-source tracking**: Add storefronts, category pages, search pages, or product pages
- **Automatic product discovery**: Crawls and discovers filament and UV resin products
- **Price history**: Tracks price changes over time with full audit trail
- **Smart parsing**: Supports JSON-LD, Shopify, WooCommerce, Magento, and generic HTML extraction
- **Compliance**: Respects robots.txt, rate limiting, and polite crawling practices
- **Scheduled scans**: Daily automated scans with manual trigger option
- **Change notifications**: Logs price changes with optional webhook/email notifications

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend development only)

### Running with Docker

1. Clone the repository:
```bash
git clone <repository-url>
cd filamentfinder
```

2. Copy environment configuration:
```bash
cp .env.example .env
```

3. Start all services:
```bash
docker compose up --build
```

4. Access the application:
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Development Setup

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

#### Worker

```bash
cd worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m worker.scheduler  # Run scheduler
python -m worker.cli scan --source-id 1  # Manual scan
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Architecture

```
filamentfinder/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── api/       # API endpoints
│   │   ├── models/    # SQLAlchemy models
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Business logic
│   │   └── core/      # Configuration
│   ├── alembic/       # Database migrations
│   └── tests/
├── worker/            # Scraper/Crawler
│   ├── parsers/       # Platform-specific parsers
│   ├── crawler/       # Crawling logic
│   └── tests/
├── frontend/          # React UI
│   └── src/
├── scripts/           # Helper scripts
└── docker-compose.yml
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `CRAWLER_USER_AGENT` | User-Agent for requests | `FilamentFinder/1.0` |
| `CRAWLER_RATE_LIMIT` | Requests per second per domain | `1.0` |
| `CRAWLER_MAX_PAGES` | Default max pages per scan | `100` |
| `CRAWLER_MAX_DEPTH` | Default max crawl depth | `3` |
| `SCAN_SCHEDULE_CRON` | Cron expression for scheduled scans | `0 6 * * *` |
| `SMTP_HOST` | SMTP server for notifications | - |
| `WEBHOOK_URL` | Webhook URL for notifications | - |

## API Endpoints

### Sources
- `POST /api/sources` - Add a new source URL
- `GET /api/sources` - List all sources
- `GET /api/sources/{id}` - Get source details
- `PUT /api/sources/{id}` - Update source
- `DELETE /api/sources/{id}` - Delete source
- `POST /api/sources/{id}/scan` - Trigger manual scan

### Products
- `GET /api/products` - List products (filter by type, source, active)
- `GET /api/products/{id}` - Product details with latest price
- `GET /api/products/{id}/history` - Price observation history
- `GET /api/products/{id}/changes` - Price change log

### Runs
- `GET /api/runs` - Crawl run history
- `GET /api/runs/{id}` - Run details with stats

## Usage Examples

### Adding a Source

```bash
curl -X POST http://localhost:8000/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example-store.com/filaments",
    "crawl_rules": {
      "max_pages": 50,
      "max_depth": 2,
      "same_domain_only": true,
      "url_patterns": ["*/filament/*", "*/pla/*"]
    }
  }'
```

### Running a Scan

```bash
curl -X POST http://localhost:8000/api/sources/1/scan
```

### Querying Products

```bash
# All filaments
curl "http://localhost:8000/api/products?type=filament"

# Price history for a product
curl "http://localhost:8000/api/products/1/history"

# Price changes in date range
curl "http://localhost:8000/api/products/1/changes?from=2024-01-01&to=2024-12-31"
```

## Product Matching

The system identifies products using keyword matching:

**Filament keywords**: filament, PLA, PETG, ABS, ASA, TPU, Nylon, PC, HIPS, PVA, wood fill, carbon fiber, silk, matte, 1.75mm, 2.85mm, 3mm

**Resin keywords**: resin, UV resin, photopolymer, 405nm, SLA, DLP, MSLA, water-washable, ABS-like, tough resin, flexible resin, castable

Products are assigned a confidence score (0-1) based on match strength.

## Compliance

- **robots.txt**: Automatically fetched and respected
- **Rate limiting**: Default 1 request/second per domain
- **Backoff**: Exponential backoff on 429/503 errors
- **User-Agent**: Clearly identifies as FilamentFinder bot
- **No bypass**: Does not attempt to bypass logins, captchas, or paywalls

## License

MIT License
