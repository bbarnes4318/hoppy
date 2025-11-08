# Quick Deploy to DigitalOcean

## Prerequisites Checklist

- [ ] GitHub repository: https://github.com/bbarnes4318/hopwhistle
- [ ] DigitalOcean account created
- [ ] Code pushed to GitHub main branch

## 5-Minute Deployment Steps

### 1. Push Code to GitHub

```bash
git add .
git commit -m "Ready for deployment"
git push origin main
```

### 2. Create Database in DigitalOcean

1. Go to: https://cloud.digitalocean.com/databases
2. Click "Create Database"
3. Select:
   - **Database Engine:** PostgreSQL 15
   - **Plan:** Basic ($15/mo) or higher
   - **Region:** Choose closest to you
   - **Name:** `hopwhistle-db`
4. Click "Create Database Cluster"
5. **Save the connection string** (you'll need it)

### 3. Deploy App via App Platform

1. Go to: https://cloud.digitalocean.com/apps
2. Click "Create App"
3. Select "GitHub" and authorize DigitalOcean
4. Select repository: `bbarnes4318/hopwhistle`
5. Select branch: `main`
6. DigitalOcean should auto-detect `.do/app.yaml` - click "Edit Plan" if needed
7. Click "Next"

### 4. Configure Database Link

1. In "Resources" section, click "Add Resource"
2. Select "Database" → Choose your `hopwhistle-db`
3. This auto-sets `DATABASE_URL` environment variable

### 5. Set Environment Variables

**For API Service:**
- `JWT_SECRET` - Generate: `openssl rand -hex 32`
- `ENABLE_TIMESCALE` - `true` (if TimescaleDB enabled)
- `CORS_ORIGINS` - Will update after web deploys
- `ENVIRONMENT` - `production`

**For Web Service:**
- `NEXT_PUBLIC_API_URL` - Will be: `https://hopwhistle-api-xxxxx.ondigitalocean.app`
- `NEXT_PUBLIC_WS_URL` - Will be: `wss://hopwhistle-api-xxxxx.ondigitalocean.app`

### 6. Deploy

1. Review settings
2. Click "Create Resources"
3. Wait 5-10 minutes for deployment

### 7. Update CORS After Deployment

1. Once deployed, note your web app URL
2. Go to API service → Settings → Environment Variables
3. Update `CORS_ORIGINS` with web app URL:
   ```
   ["https://your-web-url.ondigitalocean.app"]
   ```
4. Redeploy API service

### 8. Seed Database (Optional)

```bash
# Connect to production database temporarily
cd api
export DATABASE_URL="your-production-connection-string"
python scripts/seed.py
```

Or use DigitalOcean one-off task:
- Go to API service → Tasks → Create Task
- Command: `python scripts/seed.py`

## Verify Deployment

- ✅ API Health: `https://your-api-url/healthz` → `{"status":"ok"}`
- ✅ API Docs: `https://your-api-url/docs`
- ✅ Web App: `https://your-web-url` → Login page loads
- ✅ Login: `admin@hopwhistle.com` / `admin123` (if seeded)

## Troubleshooting

**Build fails?**
- Check logs in DigitalOcean dashboard
- Verify Dockerfile paths are correct

**Database connection fails?**
- Verify database is linked in App Platform
- Check firewall allows App Platform IPs

**CORS errors?**
- Update `CORS_ORIGINS` with actual web URL
- Use `https://` not `http://`

## Next Steps

- Set up custom domain (optional)
- Configure SSL certificates (auto-handled)
- Set up monitoring alerts
- Review logs regularly

## Cost

- **Minimum:** ~$25/month (2 services + database)
- **Recommended:** ~$40/month for better performance

