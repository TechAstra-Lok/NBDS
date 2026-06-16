# Deployment Guide

## Requirements

- Python 3.11+ installed
- `pip` available
- `virtualenv` or Python virtual environment support
- `gunicorn` installed from `requirements.txt`

## Local deployment

1. Create and activate a virtual environment:

   ```bash
   blood\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
    python run.py run --host 127.0.0.1 --port 5000
   ```

3. Copy `.env.example` to `.env` and update values.

4. Start the app locally in production mode:

   ```bash
   set FLASK_ENV=production
   set SECRET_KEY=super-secret-value
   set DATABASE_URL=sqlite:///app/nepali_blood.db
   set ADMIN_USERNAME=admin
   set ADMIN_PASSWORD=securepass
   python run.py run --host 127.0.0.1 --port 5000

   python run.py run
   ```

## Production deployment

Use the `wsgi.py` entrypoint with `gunicorn`.

```bash
gunicorn --bind 0.0.0.0:8000 wsgi:app
```

If using Heroku or any PaaS that supports Procfile, the included `Procfile` is:

```text
web: gunicorn --bind 0.0.0.0:$PORT wsgi:app
```

## Notes

- `config.py` uses `ProductionConfig` when `FLASK_ENV=production`.
- `SECRET_KEY` must be set in production; otherwise app startup will fail.
- `DATABASE_URL` may be set to any supported SQLAlchemy URL.
- Uploaded files are stored under `app/static/uploads/`.

## Docker (optional)

A simple Dockerfile and `docker-compose.yml` are included for containerized deployments.

Build the image:

```bash
docker build -t nepali_blood_donors:latest .
```

Run with Docker:

```bash
docker run -p 8000:8000 \
   -e FLASK_ENV=production \
   -e SECRET_KEY=your-secret \
   -e DATABASE_URL=sqlite:///app/nepali_blood.db \
   nepali_blood_donors:latest
```

Or with docker-compose:

```bash
docker compose up --build
```

Notes:
- The `Dockerfile` uses `python:3.11-slim` and installs system libs required for Pillow.
- When deploying to a production host, prefer mounting a persistent volume for `app/static/uploads`.

