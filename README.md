# Hopwhistle – Real-Time Lead Results Dashboard

AI-powered web app that gives publishers, brokers, and agencies instant visibility into live transfer call outcomes (billable, sales, etc.). Replace "weeks of waiting" with **real-time** dashboards, searchable transcripts, and AI summaries.

## Tech Stack

- **Frontend:** Next.js 14 (App Router), TypeScript, TailwindCSS, shadcn/ui, Zustand, React Query, Recharts
- **Backend:** FastAPI (Python 3.11+), Uvicorn, SQLAlchemy + Alembic, Pydantic v2, Postgres async (asyncpg)
- **Real-time:** FastAPI WebSockets, Postgres LISTEN/NOTIFY
- **AI/NLP:** Integration with `fefast4.py` for transcription and analysis
- **Database:** PostgreSQL with optional TimescaleDB extension

## Project Structure

```
hoppy/
├── api/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/     # API endpoints
│   │   ├── core/       # Config, database, security
│   │   ├── models/     # SQLAlchemy models
│   │   └── schemas/    # Pydantic schemas
│   └── alembic/        # Database migrations
├── web/                 # Next.js frontend
│   ├── app/            # App Router pages
│   ├── components/     # React components
│   └── lib/            # Utilities, API client, store
├── scripts/             # Utility scripts
│   ├── seed.py        # Database seeding
│   └── integrate_fefast4.py  # fefast4.py integration
└── fefast4.py          # Legacy transcription pipeline
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ (with TimescaleDB extension optional)
- Git

### Backend Setup

1. **Navigate to API directory:**
   ```bash
   cd api
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the `api/` directory:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hopwhistle
   JWT_SECRET=your-secret-key-here-change-in-production
   ENABLE_TIMESCALE=false
   CORS_ORIGINS=["http://localhost:3000"]
   OPENAI_API_KEY=optional
   DEEPSEEK_API_KEY=optional
   ```

5. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Seed database (optional):**
   ```bash
   python scripts/seed.py
   ```

7. **Start the API server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Frontend Setup

1. **Navigate to web directory:**
   ```bash
   cd web
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Set up environment variables:**
   Create a `.env.local` file in the `web/` directory:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXT_PUBLIC_WS_URL=ws://localhost:8000
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```

5. **Open your browser:**
   Navigate to `http://localhost:3000`

## Default Login Credentials

After running the seed script:

- **Admin:** `admin@hopwhistle.com` / `admin123`
- **Publisher Manager:** `manager@publisher.com` / `password123`
- **Agency Analyst:** `analyst@agency.com` / `password123`

## Integration with fefast4.py

The `fefast4.py` script can be integrated to automatically ingest call data. See `scripts/integrate_fefast4.py` for the integration helper.

To use it, modify `fefast4.py` to call the ingestion function after processing each call:

```python
from scripts.integrate_fefast4 import ingest_call_to_api

# After processing a call:
ingest_call_to_api(
    external_call_id=url_hash,
    partner_id="publisher-co",  # or UUID
    started_at=datetime.utcnow(),
    ended_at=datetime.utcnow(),
    duration_sec=131,
    disposition="connected",
    transcript=transcript,
    analysis=analysis,
    billable=True,
    sale_made=True,
    ani="+18665551212",
    dnis="+18665550000",
)
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (sets HttpOnly cookie)
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user

### Calls
- `GET /api/calls` - List calls (with filters, search, pagination)
- `GET /api/calls/{id}` - Get call details
- `GET /api/calls/{id}/transcript` - Get transcript
- `GET /api/calls/{id}/summary` - Get summary
- `POST /api/calls/ingest` - Ingest call (from fefast4.py or webhooks)

### Metrics
- `GET /api/metrics/summary` - Get KPI summary
- `GET /api/metrics/timeseries` - Get time series data for charts

### Partners
- `GET /api/partners` - List partners
- `GET /api/partners/{id}` - Get partner details

### WebSocket
- `WS /api/ws/metrics` - Real-time metrics updates

## Features

- ✅ Real-time dashboard with KPI cards
- ✅ Time-series charts (Total Calls, Billable Calls, Sales, Connected)
- ✅ Call list with filters, search, and pagination
- ✅ Call detail page with transcript viewer and summary
- ✅ Partner management
- ✅ Full-text search across transcripts
- ✅ WebSocket real-time updates
- ✅ Multi-tenancy with account isolation
- ✅ Role-based access control
- ✅ Dark mode support

## Deployment

### DigitalOcean App Platform

1. **Database:**
   - Create a Managed PostgreSQL database
   - Enable TimescaleDB extension if available
   - Note the connection string

2. **Backend (API):**
   - Connect GitHub repository
   - Set build command: `cd api && pip install -r requirements.txt`
   - Set run command: `cd api && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080`
   - Add environment variables (DATABASE_URL, JWT_SECRET, etc.)

3. **Frontend (Web):**
   - Connect GitHub repository
   - Set build command: `cd web && npm install && npm run build`
   - Set run command: `cd web && npm start`
   - Add environment variables (NEXT_PUBLIC_API_URL, etc.)

4. **Migrations:**
   - Add a GitHub Actions workflow to run migrations on deploy (see `.github/workflows/deploy.yml`)

## Development

### Running Tests

```bash
# Backend
cd api
pytest

# Frontend
cd web
npm test
```

### Code Formatting

```bash
# Backend
cd api
black .
isort .

# Frontend
cd web
npm run lint
```

## License

MIT

