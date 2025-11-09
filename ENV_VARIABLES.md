# Environment Variables Reference

## 🔴 REQUIRED Variables

### API Service (Backend)

| Variable | Type | Description | How to Get/Set |
|----------|------|-------------|----------------|
| `DATABASE_URL` | **SECRET** | PostgreSQL connection string | **Auto-set** when you link database in DigitalOcean, OR manually: `postgresql+asyncpg://user:password@host:port/dbname` |
| `JWT_SECRET` | **SECRET** | Secret key for JWT token signing | **Generate:** `openssl rand -hex 32` or use any strong random string (64+ chars) |

### Web Service (Frontend)

| Variable | Type | Description | How to Get/Set |
|----------|------|-------------|----------------|
| `NEXT_PUBLIC_API_URL` | Plain | Full URL to your API service | Set after deployment: `https://hopwhistle-api-xxxxx.ondigitalocean.app` |
| `NEXT_PUBLIC_WS_URL` | Plain | WebSocket URL for real-time updates | Set after deployment: `wss://hopwhistle-api-xxxxx.ondigitalocean.app` |

---

## 🟡 RECOMMENDED Variables

### API Service

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENVIRONMENT` | Plain | `development` | Set to `production` for production |
| `ENABLE_TIMESCALE` | Plain | `false` | Set to `true` if TimescaleDB extension is enabled |
| `CORS_ORIGINS` | Plain | `["http://localhost:3000"]` | JSON array of allowed origins. **Update after web deploys** with actual URL |

---

## 🟢 OPTIONAL Variables

### API Service

| Variable | Type | Description |
|----------|------|-------------|
| `OPENAI_API_KEY` | **SECRET** | OpenAI API key (if using OpenAI for AI features) |
| `DEEPSEEK_API_KEY` | **SECRET** | DeepSeek API key (if using DeepSeek for AI features) |
| `SPACES_ENDPOINT` | Plain | DigitalOcean Spaces endpoint (if using object storage) |
| `SPACES_KEY` | **SECRET** | DigitalOcean Spaces access key |
| `SPACES_SECRET` | **SECRET** | DigitalOcean Spaces secret key |
| `SPACES_BUCKET` | Plain | DigitalOcean Spaces bucket name |
| `JWT_ALGORITHM` | Plain | JWT algorithm (default: `HS256`) |
| `JWT_EXPIRATION_HOURS` | Plain | JWT token expiration in hours (default: `24`) |

---

## 📋 Quick Setup Checklist

### Step 1: Generate JWT Secret
```bash
# On Mac/Linux:
openssl rand -hex 32

# On Windows PowerShell:
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 64 | % {[char]$_})
```

### Step 2: Set API Service Variables

**Required:**
- ✅ `JWT_SECRET` = (your generated secret)

**Recommended:**
- ✅ `ENVIRONMENT` = `production`
- ✅ `ENABLE_TIMESCALE` = `true` (if TimescaleDB enabled)
- ✅ `CORS_ORIGINS` = `["https://your-web-url.ondigitalocean.app"]` (update after web deploys)

**Optional:**
- `OPENAI_API_KEY` = (if using OpenAI)
- `DEEPSEEK_API_KEY` = (if using DeepSeek)

### Step 3: Set Web Service Variables

**Required (set AFTER deployment):**
- ✅ `NEXT_PUBLIC_API_URL` = `https://hopwhistle-api-xxxxx.ondigitalocean.app`
- ✅ `NEXT_PUBLIC_WS_URL` = `wss://hopwhistle-api-xxxxx.ondigitalocean.app`

---

## 🔧 DigitalOcean Setup Process

### 1. Database Setup
- Create PostgreSQL database in DigitalOcean
- **DATABASE_URL is auto-set** when you link the database to your app
- No manual configuration needed!

### 2. API Service Variables
In DigitalOcean App Platform → Your API Service → Settings → Environment Variables:

```
JWT_SECRET = [your-generated-secret]
ENVIRONMENT = production
ENABLE_TIMESCALE = true
CORS_ORIGINS = ["https://hopwhistle-web-xxxxx.ondigitalocean.app"]
```

### 3. Web Service Variables
In DigitalOcean App Platform → Your Web Service → Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL = https://hopwhistle-api-xxxxx.ondigitalocean.app
NEXT_PUBLIC_WS_URL = wss://hopwhistle-api-xxxxx.ondigitalocean.app
```

**Note:** Replace `xxxxx` with your actual DigitalOcean app URL after deployment.

---

## ⚠️ Important Notes

1. **DATABASE_URL**: Automatically set when you link a database in DigitalOcean. Don't set manually unless you have a reason.

2. **CORS_ORIGINS**: Must be a valid JSON array. Use `https://` (not `http://`) in production.

3. **WebSocket URL**: Must use `wss://` (secure WebSocket) in production, not `ws://`.

4. **Secrets**: Mark sensitive variables (JWT_SECRET, API keys) as **SECRET** type in DigitalOcean to encrypt them.

5. **Update After Deploy**: `CORS_ORIGINS` and web service URLs need to be updated after initial deployment with actual DigitalOcean URLs.

---

## 🧪 Testing Locally

For local development, create these files:

**`api/.env`:**
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hopwhistle
JWT_SECRET=your-local-secret-key-change-in-production
ENABLE_TIMESCALE=false
CORS_ORIGINS=["http://localhost:3000"]
ENVIRONMENT=development
```

**`web/.env.local`:**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 📝 Example Values

### Production Example (DigitalOcean)

**API Service:**
```
DATABASE_URL = postgresql+asyncpg://hopwhistle:password@db.ondigitalocean.com:25060/hopwhistle?sslmode=require
JWT_SECRET = a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2
ENVIRONMENT = production
ENABLE_TIMESCALE = true
CORS_ORIGINS = ["https://hopwhistle-web-abc123.ondigitalocean.app"]
```

**Web Service:**
```
NEXT_PUBLIC_API_URL = https://hopwhistle-api-xyz789.ondigitalocean.app
NEXT_PUBLIC_WS_URL = wss://hopwhistle-api-xyz789.ondigitalocean.app
```

