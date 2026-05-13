# Deploy Runbook

This repo is ready to deploy with Docker Compose on Coolify or a similar platform.

## Compose Files

Use both files:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

`docker-compose.yml` defines the stack. `docker-compose.prod.yml` disables backend hot reload and adds one-off operational services.

## Required Environment

Set production values in the platform secret manager:

- `APP_ENV=production`
- `APP_DEBUG=false`
- `APP_CORS_ORIGINS=https://<frontend-domain>`
- `NEXT_PUBLIC_API_URL=https://<backend-domain>`
- `NEXT_PRIVATE_API_URL=https://<backend-domain>`
- `NEXTAUTH_URL=https://<frontend-domain>`
- `JWT_SECRET`
- `NEXTAUTH_SECRET`
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_PUBLIC_ENDPOINT`, `MINIO_BUCKET_ILLUSTRATIONS`
- `LLM_PROVIDER=gemini` with `GEMINI_API_KEY`, or `LLM_PROVIDER=openrouter` with `OPENROUTER_API_KEY`
- `GEMINI_IMAGE_MODEL` and `ILLUSTRATION_DAILY_LIMIT` if chat concept illustrations are enabled
- `DEMO_PARENT_PASSWORD` for the one-off `demo-seed` command

## Post-Deploy Commands

Run migrations:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
```

Seed the demo family:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm demo-seed
```

Demo login:

```text
ayse@demo.cuzdan-kocu.app / <DEMO_PARENT_PASSWORD>
```

Refresh proactive insights:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm proactive-worker
```

Schedule the same proactive worker command daily at `04:00 UTC`.

## Verification

After DNS/HTTPS is configured:

1. Open `https://<backend-domain>/health` and expect `{"status":"ok","version":"0.1.0"}`.
2. Open `https://<frontend-domain>` and log in with the demo family.
3. Confirm `/dashboard` shows an API-backed koç notu.
4. Confirm `/family` lists Ayşe and Elif with `is_demo=true` seed data; Mehmet has a separate demo parent login if needed.
5. Switch into Elif and ask chat `Faiz nedir?`.

The actual live URL must be verified on the deployment platform before Task 9 can be marked fully done.
