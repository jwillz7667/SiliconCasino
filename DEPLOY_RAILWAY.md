# Deploying Silicon Casino to Railway

This guide walks through deploying the Silicon Casino backend and database to Railway via GitHub.

## Prerequisites

- GitHub repository with your code pushed
- Railway account (https://railway.app)

---

## Step 1: Push Code to GitHub

```bash
cd "/Users/willz/ai/silicon casino"

# Initialize git if needed
git init

# Add all files
git add .

# Commit
git commit -m "Phase 3: Code Golf, PWA, Referrals, Admin Panel"

# Add remote and push
git remote add origin https://github.com/YOUR_USERNAME/silicon-casino.git
git push -u origin main
```

---

## Step 2: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your GitHub account if not already connected
5. Select your `silicon-casino` repository
6. Railway will auto-detect the Dockerfile and start building

---

## Step 3: Add PostgreSQL Database

1. In your Railway project, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway automatically sets `DATABASE_URL` for your backend service

---

## Step 4: Add Redis

1. Click **"+ New"** again
2. Select **"Database"** → **"Add Redis"**
3. Railway automatically sets `REDIS_URL` for your backend service

---

## Step 5: Configure Environment Variables

1. Click on your backend service (the GitHub deployment)
2. Go to **"Variables"** tab
3. Add these variables:

### Required Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `ENVIRONMENT` | `production` | Production mode |
| `DEBUG` | `false` | Disable debug logging |
| `SECRET_KEY` | `<generate-secure-key>` | JWT signing secret |

Generate a secure secret key:
```bash
openssl rand -base64 32
```

### Push Notifications (Optional)

| Variable | Value |
|----------|-------|
| `VAPID_PRIVATE_KEY` | Your VAPID private key |
| `VAPID_PUBLIC_KEY` | Your VAPID public key |
| `VAPID_EMAIL` | `admin@yourdomain.com` |

Generate VAPID keys:
```bash
npm install -g web-push
web-push generate-vapid-keys
```

### Crypto/Blockchain (Optional)

| Variable | Value |
|----------|-------|
| `POLYGON_RPC_URL` | `https://polygon-rpc.com` or Infura/Alchemy URL |
| `HOT_WALLET_PRIVATE_KEY` | Your wallet private key (keep secure!) |

---

## Step 6: Configure Build Settings

Railway should auto-detect the Dockerfile. If not:

1. Click on your service
2. Go to **"Settings"** tab
3. Under **"Build"**, set:
   - **Builder**: Dockerfile
   - **Dockerfile Path**: `Dockerfile`

---

## Step 7: Deploy

Railway automatically deploys when you push to GitHub. You can also:

1. Click **"Deploy"** button in the service settings
2. Or trigger via Railway CLI: `railway up`

---

## Step 8: Generate Domain

1. Click on your backend service
2. Go to **"Settings"** tab
3. Under **"Networking"** → **"Public Networking"**
4. Click **"Generate Domain"**
5. You'll get a URL like: `silicon-casino-production.up.railway.app`

---

## Step 9: Verify Deployment

```bash
# Check health endpoint
curl https://your-app.up.railway.app/health
# Should return: {"status": "healthy"}

# Check API docs
open https://your-app.up.railway.app/docs
```

---

## Project Structure on Railway

After setup, your Railway project should look like:

```
Silicon Casino (Project)
├── Backend Service (from GitHub)
│   └── Dockerfile deployment
├── PostgreSQL
│   └── DATABASE_URL auto-linked
└── Redis
    └── REDIS_URL auto-linked
```

---

## Automatic Deployments

Railway automatically deploys when you push to your connected branch:

```bash
# Make changes locally
git add .
git commit -m "Update feature"
git push origin main

# Railway detects push and redeploys automatically
```

---

## Viewing Logs

1. Click on your backend service
2. Go to **"Deployments"** tab
3. Click on active deployment
4. View real-time logs

Or via CLI:
```bash
railway logs
```

---

## Running Database Migrations

Migrations run automatically on deploy (see Dockerfile CMD).

To run manually:
```bash
# Via Railway CLI
railway run alembic upgrade head

# Or connect to shell
railway shell
alembic upgrade head
```

---

## Environment Variables Reference

### Auto-Set by Railway
| Variable | Set By |
|----------|--------|
| `DATABASE_URL` | PostgreSQL plugin |
| `REDIS_URL` | Redis plugin |
| `PORT` | Railway (usually 8000) |

### You Must Set
| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ Yes | JWT signing secret |
| `ENVIRONMENT` | ✅ Yes | Set to `production` |
| `DEBUG` | ✅ Yes | Set to `false` |
| `VAPID_PRIVATE_KEY` | For push | Web Push private key |
| `VAPID_PUBLIC_KEY` | For push | Web Push public key |
| `POLYGON_RPC_URL` | For crypto | Blockchain RPC |
| `HOT_WALLET_PRIVATE_KEY` | For crypto | Withdrawal wallet |

---

## Frontend Deployment

Deploy frontend separately to Vercel (recommended for React):

```bash
cd frontend

# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Set environment variable for API URL
vercel env add VITE_API_URL
# Enter: https://your-backend.up.railway.app
```

Or deploy to Railway as separate service:
1. Create new service in same project
2. Point to `frontend` directory
3. Set build command: `npm run build`
4. Set start command: `npx serve dist`

---

## Scaling

### Horizontal Scaling
1. Go to service **Settings**
2. Under **"Deploy"**, increase **"Replicas"**

### Database Scaling
1. Click on PostgreSQL service
2. Upgrade plan for more resources

---

## Troubleshooting

### Build Fails
- Check Dockerfile syntax
- Ensure all files are committed to Git
- Check Railway build logs

### Database Connection Fails
- Verify PostgreSQL service is running
- Check `DATABASE_URL` is set in backend service
- Ensure services are in same project (auto-linking)

### Migrations Fail
- Check database is accessible
- Review migration files for errors
- Run `railway run alembic history` to check state

### WebSocket Issues
- Railway supports WebSockets on all plans
- Ensure client connects to wss:// (not ws://)

---

## Cost Estimate

Railway pricing (as of 2024):
- **Hobby Plan**: $5/month includes:
  - 512MB RAM per service
  - Shared CPU
  - 1GB PostgreSQL
  - 100MB Redis

- **Pro Plan**: $20/month includes:
  - 8GB RAM per service
  - Dedicated CPU
  - Larger databases
  - Team features

For Silicon Casino with moderate traffic:
- Backend: ~$5-10/month
- PostgreSQL: ~$5-10/month
- Redis: ~$5/month
- **Total**: ~$15-25/month

---

## Security Checklist

- [ ] `SECRET_KEY` is unique and secure (32+ random bytes)
- [ ] `DEBUG` is set to `false`
- [ ] `ENVIRONMENT` is set to `production`
- [ ] Database credentials not exposed in code
- [ ] `HOT_WALLET_PRIVATE_KEY` stored securely (if using crypto)
- [ ] CORS configured for your frontend domain
- [ ] Rate limiting enabled (default in Phase 3)
