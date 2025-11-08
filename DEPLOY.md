# DigitalOcean App Platform Deployment Guide

This guide will help you deploy Hopwhistle to DigitalOcean App Platform.

## Prerequisites

1. A DigitalOcean account
2. GitHub repository: https://github.com/bbarnes4318/hopwhistle
3. DigitalOcean API token (for GitHub Actions, optional)

## Step 1: Push Code to GitHub

First, ensure all your code is committed and pushed to the repository:

```bash
# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Hopwhistle dashboard"

# Add remote (if not already added)
git remote add origin https://github.com/bbarnes4318/hopwhistle.git

# Push to main branch
git branch -M main
git push -u origin main
```

## Step 2: Create DigitalOcean Database

1. Go to DigitalOcean Dashboard → Databases
2. Create a new PostgreSQL database:
   - **Name:** `hopwhistle-db`
   - **Version:** PostgreSQL 15
   - **Region:** Choose your preferred region (e.g., NYC)
   - **Plan:** Choose based on your needs (Basic $15/mo minimum)
   - **Enable TimescaleDB** if available (recommended)

3. **Important:** Note down the connection string from the database settings
   - Format: `postgresql+asyncpg://user:password@host:port/dbname`

## Step 3: Deploy via DigitalOcean App Platform

### Option A: Using App Platform UI (Recommended)

1. Go to DigitalOcean Dashboard → Apps → Create App
2. Connect your GitHub repository: `bbarnes4318/hopwhistle`
3. Select the `main` branch
4. DigitalOcean will auto-detect the `.do/app.yaml` file

   **OR** configure manually:

#### Backend API Service:
- **Name:** `api`
- **Type:** Service
- **Source:** GitHub (bbarnes4318/hopwhistle, main branch)
- **Dockerfile Path:** `api/Dockerfile`
- **Dockerfile Context:** `api`
- **HTTP Port:** `8080`
- **HTTP Request Routes:** `/api`
- **Run Command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080`
- **Health Check Path:** `/healthz`

**Environment Variables:**
- `DATABASE_URL` - (Secret) Your PostgreSQL connection string
- `JWT_SECRET` - (Secret) Generate a strong random secret
- `ENABLE_TIMESCALE` - `true` (if TimescaleDB is enabled)
- `CORS_ORIGINS` - `["https://your-web-app-url.ondigitalocean.app"]`
- `ENVIRONMENT` - `production`
- `OPENAI_API_KEY` - (Secret, optional)
- `DEEPSEEK_API_KEY` - (Secret, optional)

#### Frontend Web Service:
- **Name:** `web`
- **Type:** Service
- **Source:** GitHub (bbarnes4318/hopwhistle, main branch)
- **Dockerfile Path:** `web/Dockerfile`
- **Dockerfile Context:** `web`
- **HTTP Port:** `3000`
- **HTTP Request Routes:** `/`
- **Health Check Path:** `/`

**Environment Variables:**
- `NEXT_PUBLIC_API_URL` - `https://your-api-app-url.ondigitalocean.app`
- `NEXT_PUBLIC_WS_URL` - `wss://your-api-app-url.ondigitalocean.app`

5. **Link Database:**
   - In the App Platform settings, go to "Components" → "Databases"
   - Link your `hopwhistle-db` database
   - This will automatically set `DATABASE_URL` environment variable

6. **Deploy:**
   - Click "Create Resources" or "Deploy"
   - Wait for deployment to complete (5-10 minutes)

### Option B: Using doctl CLI

```bash
# Install doctl
# macOS: brew install doctl
# Linux: See https://docs.digitalocean.com/reference/doctl/how-to/install/

# Authenticate
doctl auth init

# Deploy app
doctl apps create --spec .do/app.yaml
```

## Step 4: Run Database Migrations

After deployment, migrations should run automatically via the `run_command` in the Dockerfile. To verify:

1. Go to your API service logs in DigitalOcean
2. Check for "Running migrations..." and "Migration complete"
3. If migrations fail, you can run them manually:

```bash
# SSH into your app (if possible) or use a one-off task
doctl apps create-deployment <app-id> --force-rebuild
```

## Step 5: Seed Database (Optional)

To seed the database with test data, you can:

1. **Option A:** Run locally and connect to production DB (temporary)
   ```bash
   cd api
   # Set DATABASE_URL to production connection string
   export DATABASE_URL="postgresql+asyncpg://..."
   python scripts/seed.py
   ```

2. **Option B:** Create a one-off task in DigitalOcean App Platform
   - Go to your API service
   - Create a one-off task
   - Run command: `python scripts/seed.py`

## Step 6: Update CORS Settings

After deployment, update the `CORS_ORIGINS` environment variable in your API service with the actual web app URL:

1. Go to App Platform → Your API Service → Settings → Environment Variables
2. Update `CORS_ORIGINS` with your actual web app URL:
   ```
   ["https://hopwhistle-web-xxxxx.ondigitalocean.app"]
   ```
3. Redeploy the API service

## Step 7: Verify Deployment

1. **Check API Health:**
   ```
   https://your-api-url.ondigitalocean.app/healthz
   ```
   Should return: `{"status":"ok"}`

2. **Check API Docs:**
   ```
   https://your-api-url.ondigitalocean.app/docs
   ```

3. **Access Web App:**
   ```
   https://your-web-url.ondigitalocean.app
   ```

4. **Login:**
   - If you seeded the database: `admin@hopwhistle.com` / `admin123`
   - Otherwise, create a user via API or database directly

## Environment Variables Reference

### API Service Required Variables:
- `DATABASE_URL` - PostgreSQL connection string (auto-set if database is linked)
- `JWT_SECRET` - Secret key for JWT tokens (generate a strong random string)

### API Service Optional Variables:
- `ENABLE_TIMESCALE` - Set to `"true"` if TimescaleDB is enabled
- `CORS_ORIGINS` - JSON array of allowed origins
- `OPENAI_API_KEY` - For AI features
- `DEEPSEEK_API_KEY` - For AI features
- `ENVIRONMENT` - Set to `"production"`

### Web Service Required Variables:
- `NEXT_PUBLIC_API_URL` - Full URL to your API service
- `NEXT_PUBLIC_WS_URL` - WebSocket URL (wss:// for production)

## Troubleshooting

### Database Connection Issues
- Verify `DATABASE_URL` is set correctly
- Check database firewall rules allow App Platform IPs
- Ensure database is in the same region as your app

### Migration Failures
- Check logs in DigitalOcean App Platform
- Verify database user has CREATE/ALTER permissions
- Try running migrations manually via one-off task

### CORS Errors
- Ensure `CORS_ORIGINS` includes your web app URL
- Check that URLs use HTTPS in production
- Verify WebSocket URL uses `wss://` not `ws://`

### Build Failures
- Check Dockerfile paths are correct
- Verify all dependencies are in requirements.txt/package.json
- Review build logs in DigitalOcean dashboard

## Continuous Deployment

Once set up, every push to the `main` branch will automatically trigger a new deployment if `deploy_on_push: true` is set in the app.yaml.

## Monitoring

- **Logs:** View real-time logs in DigitalOcean App Platform dashboard
- **Metrics:** Monitor CPU, memory, and request metrics
- **Alerts:** Set up alerts for errors or high resource usage

## Cost Estimation

- **Basic App Service:** ~$5-12/month per service (2 services = $10-24/month)
- **PostgreSQL Database:** ~$15/month (Basic plan)
- **Total:** ~$25-40/month minimum

## Support

For issues:
1. Check DigitalOcean App Platform logs
2. Review application logs
3. Verify environment variables
4. Check database connectivity
5. Review GitHub Actions logs (if using CI/CD)

