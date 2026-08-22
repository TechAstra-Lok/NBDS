# 🩸 रक्तदान र रक्तदाता — Deployment Guide

Complete guide to run the app locally and deploy it live at `raktadata.lokeshprasai.com.np`.

---

## Table of Contents

1. [Local Development](#1-local-development)
2. [Environment Variables Reference](#2-environment-variables-reference)
3. [Deploy to Render (Free)](#3-deploy-to-render-free)
4. [Custom Domain via Cloudflare DNS](#4-custom-domain-via-cloudflare-dns)
5. [Database — SQLite vs PostgreSQL](#5-database--sqlite-vs-postgresql)
6. [Docker (Optional)](#6-docker-optional)

---

## 1. Local Development

### Prerequisites
- Python 3.11+
- Git

### Steps

```bash
# 1. Activate the virtual environment (Windows)
.\blood\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file and fill in values
copy .env.example .env

# 4. Run the development server
python run.py run --host 127.0.0.1 --port 5000
```

The app will be available at: **http://127.0.0.1:5000**

> **Note:** On first run, the database tables are created automatically via `db.create_all()`.
> To apply Alembic migrations instead: `flask db upgrade`

---

## 2. Environment Variables Reference

Copy `.env.example` to `.env` and update all values before running:

| Variable | Required | Description |
|---|---|---|
| `FLASK_ENV` | ✅ | `production` in live, `development` locally |
| `SECRET_KEY` | ✅ | Long random string — app will refuse to start without this |
| `DATABASE_URL` | ✅ | SQLite path or PostgreSQL connection string |
| `ADMIN_USERNAME` | ✅ | First superadmin account username |
| `ADMIN_PASSWORD` | ✅ | First superadmin account password |
| `ADMIN_EMAIL` | ✅ | Superadmin email address |
| `SITE_NAME` | ❌ | Overrides `config.py` site name if set |
| `SITE_TAGLINE` | ❌ | Overrides tagline |
| `GA_TRACKING_ID` | ❌ | Google Analytics 4 Measurement ID |
| `GEMINI_API_KEY` | ❌ | Google Gemini API key (for AI features) |
| `MAX_CONTENT_LENGTH` | ❌ | Max upload size in bytes (default: 16 MB) |

> ⚠️ **Never commit your `.env` file.** It is already in `.gitignore`.

### Generate a secure SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Deploy to Render (Free)

> **GitHub Repository:** https://github.com/TechAstra-Lok/NBDS

### Step 1 — Create a Web Service

1. Go to https://render.com and sign in (use GitHub login).
2. Click **New +** → **Web Service**.
3. Connect GitHub and select repository: **`TechAstra-Lok/NBDS`**.

### Step 2 — Configure the Service

| Field | Value |
|---|---|
| **Name** | `raktadata` |
| **Region** | Singapore (closest to Nepal) |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn wsgi:app` |
| **Instance Type** | Free |

### Step 3 — Set Environment Variables

In **Advanced → Environment Variables**, add:

| Key | Value |
|---|---|
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | *(generate with command above)* |
| `DATABASE_URL` | `sqlite:///app/nepali_blood.db` or PostgreSQL URL |
| `ADMIN_USERNAME` | *(your admin username)* |
| `ADMIN_PASSWORD` | *(your secure admin password)* |
| `ADMIN_EMAIL` | *(your admin email)* |

### Step 4 — Deploy

Click **Create Web Service**. Render will:
1. Pull code from GitHub
2. Run `pip install -r requirements.txt`
3. Start the app with `gunicorn wsgi:app`
4. Assign a URL like `https://raktadata.onrender.com`

> 💡 **Auto-deploy:** Every `git push origin main` triggers a new deployment automatically.

---

## 4. Custom Domain via Cloudflare DNS

Target URL: **`https://raktadata.lokeshprasai.com.np`**

### Step 1 — Add Custom Domain in Render

1. Open your Render Web Service → **Settings** tab.
2. Scroll to **Custom Domains** → click **Add Custom Domain**.
3. Enter: `raktadata.lokeshprasai.com.np`
4. Click **Save** — Render shows a **CNAME target** (e.g. `raktadata.onrender.com`).

### Step 2 — Add DNS Record in Cloudflare

1. Log in to https://dash.cloudflare.com
2. Select domain: `lokeshprasai.com.np`
3. Go to **DNS → Records → Add record**

| Field | Value |
|---|---|
| **Type** | `CNAME` |
| **Name** | `raktadata` |
| **Target** | `raktadata.onrender.com` *(from Render)* |
| **Proxy status** | Proxied (Orange Cloud) |
| **TTL** | Auto |

4. Click **Save**.

### Step 3 — Configure SSL in Cloudflare

1. Go to **SSL/TLS** tab in Cloudflare.
2. Set encryption mode to **Full** (not "Flexible").

> ⚠️ Using "Flexible" mode with Render causes redirect loops. Always use **Full**.

### Step 4 — Verify

1. Back in Render → **Custom Domains** → click **Verify**.
2. Render automatically issues a **free Let's Encrypt SSL certificate**.
3. Wait 2–5 minutes, then open: **https://raktadata.lokeshprasai.com.np** ✅

---

## 5. Database — SQLite vs PostgreSQL

### SQLite (default)

```
DATABASE_URL=sqlite:///app/nepali_blood.db
```

> 🚨 **CRITICAL WARNING — DATA DELETION ON RENDER FREE TIER:** 
> Render free web services use **ephemeral storage**. This means that **every time the service restarts, sleeps, or redeploys**, the local SQLite database (`nepali_blood.db`) is entirely wiped out and reset. This causes all newly registered donors, requests, and updates to be deleted.
> 
> **To fix this and make donor data permanent**, you MUST use an external PostgreSQL database (Render provides a free PostgreSQL database).

### PostgreSQL (recommended for production)

1. In Render Dashboard → **New +** → **PostgreSQL** (free tier available).
2. Copy the **Internal Database URL**.
3. Set environment variable:

```
DATABASE_URL=postgresql://user:password@host/dbname
```

4. On first deploy, run migrations:

```bash
flask db upgrade
```

---

## 6. Docker (Optional)

A `Dockerfile` and `docker-compose.yml` are included for local containerized testing.

### Build and Run

```bash
# Build the image
docker build -t raktadata:latest .

# Run the container
docker run -p 8000:8000 \
  -e FLASK_ENV=production \
  -e SECRET_KEY=your-secret-key \
  -e DATABASE_URL=sqlite:///app/nepali_blood.db \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=securepass \
  raktadata:latest
```

### Or with docker-compose

```bash
docker compose up --build
```

Open: **http://localhost:8000**

---

## Procfile

The included `Procfile` is compatible with Render, Railway, and Heroku:

```
web: gunicorn --bind 0.0.0.0:$PORT wsgi:app
```

---

## Summary — Zero Cost Hosting Stack

| Component | Provider | Cost |
|---|---|---|
| Domain (`.com.np`) | Nepal Mercantile | FREE |
| DNS + Subdomain + SSL Proxy | Cloudflare Free | FREE |
| App Hosting | Render Free Tier | FREE |
| SSL Certificate | Let's Encrypt (via Render) | FREE |
| Database | Render PostgreSQL Free Tier | FREE |
| **Live URL** | `https://raktadata.lokeshprasai.com.np` | **FREE** |


