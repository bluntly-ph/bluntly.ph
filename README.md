# Bluntly.ph

[![Status: In development](https://img.shields.io/badge/Status-In%20development-yellow)](docs/frontend/index.md)
[![Frontend: Next.js 16](https://img.shields.io/badge/Frontend-Next.js%2016-black)](docs/frontend/index.md)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](docs/MILESTONES.md)
[![Docs: FMD](https://img.shields.io/badge/Docs-FMD-333)](docs/frontend/index.md)

A verified product and seller review platform for Filipino online shoppers: read and write
blunt, structured, proof-backed reviews, evaluate sellers, and earn through an honest token
economy. This repo is a monorepo with a Next.js frontend at the root and a FastAPI backend in
`backend/`.

## Getting started

```bash
# Frontend (repo root)
npm install
npm run dev            # http://localhost:3000
npm run gen:api        # regenerate lib/api-types.d.ts from docs/openapi.json

# Backend (separate track)
cd backend && docker compose up -d --build   # http://localhost:8000
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` for local development. The backend's
`CORS_ORIGINS` must include the frontend origin.

## Documentation

The two tracks have separate documentation suites.

**Frontend** (built with the FMD documentation engine); [`docs/frontend/`](docs/frontend/index.md):

- [Index / manifest](docs/frontend/index.md)
- [PRD](docs/frontend/prd-bluntly-fe.md); screens and features by milestone (FE-M1 / FE-M2 / FE-M3)
- [Design system](docs/frontend/dsd-bluntly-fe.md) (+ root [`BRAND.md`](BRAND.md), [`DESIGN.md`](DESIGN.md))
- [System design](docs/frontend/sdd-bluntly-fe.md); Next.js architecture and API integration
- [QA & test plan](docs/frontend/qad-bluntly-fe.md)
- [Build guide](docs/frontend/build-bluntly-fe.md) (materialized to root [`AGENTS.md`](AGENTS.md))

**Backend**; [`docs/`](docs/):

- [Milestones (M1;M3)](docs/MILESTONES.md), [As-built architecture](docs/ARCHITECTURE_AS_BUILT.md), [Data dictionary](docs/schema.md)
- [Frontend integration contract](docs/FRONTEND_INTEGRATION.md), [OpenAPI spec](docs/openapi.json)
- [Production runbook](docs/PRODUCTION.md)

## Repo layout

```
app/        Next.js App Router frontend (routes, layouts)
lib/        shared frontend logic + generated API types
public/      static assets
backend/     FastAPI backend (separate track, built through M3)
docs/        backend docs + docs/frontend/ (frontend suite)
```

## Stack

Frontend: Next.js 16.2.10, React 19.2.4, Tailwind CSS v4, TypeScript. Backend: FastAPI,
SQLAlchemy, Alembic, Celery, Redis, PostgreSQL / Supabase.
