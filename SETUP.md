# Quick Setup Guide

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Git

## Quick Start

### 1. Database Setup

```bash
# Create PostgreSQL database
createdb hopwhistle

# Or using psql:
psql -U postgres
CREATE DATABASE hopwhistle;
```

### 2. Backend Setup

```bash
cd api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file (copy from .env.example)
cp .env.example .env
# Edit .env with your DATABASE_URL and JWT_SECRET

# Run migrations
alembic upgrade head

# Seed database (optional)
python scripts/seed.py

# Start server
uvicorn app.main:app --reload
```

### 3. Frontend Setup

```bash
cd web

# Install dependencies
npm install

# Create .env.local file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
echo "NEXT_PUBLIC_WS_URL=ws://localhost:8000" >> .env.local

# Start dev server
npm run dev
```

### 4. Access the Application

- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- Login: `admin@hopwhistle.com` / `admin123` (after seeding)

## Environment Variables

### Backend (`api/.env`)

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hopwhistle
JWT_SECRET=your-secret-key-change-in-production
ENABLE_TIMESCALE=false
CORS_ORIGINS=["http://localhost:3000"]
```

### Frontend (`web/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Testing the Integration

1. Start both backend and frontend
2. Login at http://localhost:3000/login
3. View dashboard at http://localhost:3000/dashboard
4. View calls at http://localhost:3000/calls

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running
- Check DATABASE_URL format: `postgresql+asyncpg://user:pass@host:port/db`
- Verify database exists

### Migration Issues

- Ensure all models are imported in `api/app/models/__init__.py`
- Check Alembic version: `alembic current`
- Reset if needed: `alembic downgrade base && alembic upgrade head`

### Frontend Build Issues

- Clear `.next` folder: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`

## Next Steps

- Review the README.md for detailed documentation
- Check API documentation at http://localhost:8000/docs
- Integrate fefast4.py using `scripts/integrate_fefast4.py`

