# DigitalOcean App Platform Setup - Manual Configuration

If DigitalOcean doesn't auto-detect your components, follow these steps to configure manually:

## Step 1: Create App in DigitalOcean

1. Go to: https://cloud.digitalocean.com/apps
2. Click **"Create App"**
3. Select **"GitHub"** and authorize DigitalOcean
4. Select repository: `bbarnes4318/hopwhistle`
5. Select branch: `main`
6. Click **"Next"**

## Step 2: Configure API Service (Backend)

If auto-detection fails, click **"Edit"** or **"Add Component"**:

### API Service Settings:
- **Type:** Service
- **Name:** `api`
- **Source Directory:** `api`
- **Build Command:** (leave empty - Dockerfile handles it)
- **Run Command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080`
- **HTTP Port:** `8080`
- **HTTP Request Routes:** `/api`
- **Health Check Path:** `/healthz`

### API Dockerfile Settings:
- **Dockerfile Path:** `api/Dockerfile`
- **Dockerfile Context:** `api`

### API Environment Variables:
Add these in the Environment Variables section:

```
DATABASE_URL = [Will be auto-set when you link database]
JWT_SECRET = [Generate: openssl rand -hex 32]
ENVIRONMENT = production
ENABLE_TIMESCALE = true
CORS_ORIGINS = ["https://hopwhistle-web.ondigitalocean.app"]
```

## Step 3: Configure Web Service (Frontend)

Click **"Add Component"** → **"Service"**:

### Web Service Settings:
- **Type:** Service
- **Name:** `web`
- **Source Directory:** `web`
- **Build Command:** (leave empty - Dockerfile handles it)
- **Run Command:** `npm start`
- **HTTP Port:** `3000`
- **HTTP Request Routes:** `/`
- **Health Check Path:** `/`

### Web Dockerfile Settings:
- **Dockerfile Path:** `web/Dockerfile`
- **Dockerfile Context:** `web`

### Web Environment Variables:
Add these AFTER deployment (update with actual URLs):

```
NEXT_PUBLIC_API_URL = https://hopwhistle-api-xxxxx.ondigitalocean.app
NEXT_PUBLIC_WS_URL = wss://hopwhistle-api-xxxxx.ondigitalocean.app
```

## Step 4: Create/Link Database

1. In the App Platform setup, go to **"Resources"** section
2. Click **"Add Resource"** → **"Database"**
3. Either:
   - **Create New:** PostgreSQL 15, Basic plan ($15/mo)
   - **Link Existing:** Select your existing database
4. This will auto-set `DATABASE_URL` for your API service

## Step 5: Review and Deploy

1. Review all settings
2. Click **"Create Resources"** or **"Deploy"**
3. Wait 5-10 minutes for deployment

## Step 6: Update URLs After Deployment

After deployment, you'll get URLs like:
- API: `https://hopwhistle-api-abc123.ondigitalocean.app`
- Web: `https://hopwhistle-web-xyz789.ondigitalocean.app`

### Update API Service:
1. Go to API service → Settings → Environment Variables
2. Update `CORS_ORIGINS`:
   ```
   ["https://hopwhistle-web-xyz789.ondigitalocean.app"]
   ```

### Update Web Service:
1. Go to Web service → Settings → Environment Variables
2. Update:
   ```
   NEXT_PUBLIC_API_URL = https://hopwhistle-api-abc123.ondigitalocean.app
   NEXT_PUBLIC_WS_URL = wss://hopwhistle-api-abc123.ondigitalocean.app
   ```
3. Redeploy web service

## Troubleshooting

### "No components detected"
- Make sure `api/Dockerfile` and `web/Dockerfile` exist
- Verify `api/requirements.txt` and `web/package.json` exist
- Try configuring manually using steps above

### Build fails
- Check logs in DigitalOcean dashboard
- Verify Dockerfile paths are correct
- Ensure all dependencies are in requirements.txt/package.json

### Database connection fails
- Verify database is linked in App Platform
- Check `DATABASE_URL` is set correctly
- Ensure database firewall allows App Platform IPs

