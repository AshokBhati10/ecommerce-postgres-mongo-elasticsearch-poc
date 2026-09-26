# E-commerce POC — PostgreSQL + MongoDB + Elasticsearch

A polyglot-persistence proof of concept for the course assignment
(`workspace/user/files/ecommerce-postgres-mongo-es.pdf`): one e-commerce app,
three databases, each owning what it is best at.

| Database   | Owns                                             | Screens                        |
|------------|--------------------------------------------------|--------------------------------|
| PostgreSQL | Canonical orders/users: ACID transactions        | Checkout (write), Order details |
| MongoDB    | Product catalog: nested docs, variants           | Storefront, Catalog admin      |
| Elasticsearch | Order search + aggregations                   | Admin search                   |

**Write-path discipline:** PostgreSQL is the system of record. Every order is
inserted in a single ACID transaction; MongoDB is read for validation; ES is a
derived index rebuilt from PostgreSQL, never written directly by user code.

## Stack

Python 3.11+ · FastAPI/Uvicorn · Vue 3/Vite · PostgreSQL 16 · MongoDB 8 ·
Elasticsearch 8.15 · Docker Compose

## Quickstart (Docker)

```bash
cp .env.example .env
docker compose up -d

# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed        # schema + 8 users + 26 products + 42 orders + ES index
uvicorn app.main:app --reload

# frontend (new shell)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

## Without Docker (native services)

Point the `.env` at your local Postgres/Mongo/ES instances (see `.env.example`),
then run the same backend/frontend steps above.

## Seed data (reproducible)

`python -m scripts.seed` wipes and rebuilds everything deterministically:

- 8 users (incl. `John Doe`, `Wendy Wireless`)
- 26 products (25 active, 1 inactive) across `peripherals`, `audio`,
  `cables`, `office` (≥ 5 each), with nested attributes, variants, and tags
- 42 orders / 96 items, statuses balanced 14/14/14 (PENDING/PROCESSING/SHIPPED)
- deliberate fixture: order history keeps the snapshot `Wireless Mouse`
  ($50.16) while the live catalog sells `Wireless Mouse Pro` ($59.99) —
  this proves checkout snapshots instead of referencing live catalog data

## The five screens

1. `/` — **Storefront** (MongoDB): product grid, category/text filters
2. `/checkout` — **Checkout**: validates against Mongo, transactional insert in
   Postgres, syncs ES
3. `/admin` — **Admin search** (Elasticsearch only): omni-search, status/date/
   price facets, revenue + per-status aggregations
4. `/admin/orders/:id` — **Order details** (PostgreSQL canonical): receipt,
   status update, ES in-sync badge
5. `/admin/catalog` — **Catalog admin** (MongoDB): create/edit products with
   tags, attributes, variants

## Sync strategies (Postgres → Elasticsearch)

Configured via `SYNC_STRATEGY`:

- **`dual_write`** (default): after the order transaction commits, the API
  writes the same canonical document to ES. Low latency (~ms), but if ES is
  down the doc is missing until something else fixes it.
- **`polling`**: a background worker (every `POLL_INTERVAL_SECONDS`) bulk-indexes
  orders newer than its watermark. Orders appear in ES within one interval —
  eventual consistency, self-healing after ES outages.

### Comparing them (demo)

```bash
# Terminal 1: run the API in polling mode with a short interval
SYNC_STRATEGY=polling POLL_INTERVAL_SECONDS=3 uvicorn app.main:app

# Terminal 2: place an order, then immediately check ES sync status
curl -X POST localhost:8000/api/orders -H 'Content-Type: application/json' \
  -d '{"user_id":1,"items":[{"product_id":"<id>","quantity":1}]}'
# -> "es_synced": false ... a few seconds later GET /api/orders/<id>
# -> "es_in_sync": true (the worker caught up)
```

- **Latency:** dual-write is visible in Screen 3 instantly; polling lags up to
  one interval (watch the sync badge on Screen 4 flip from out-of-sync to
  in-sync).
- **ES down for 5 minutes:** dual-write keeps taking orders (Postgres is the
  source of truth) but new docs pile up unsynced — recover with
  `python -m scripts.reindex_orders`. Polling retries every interval and heals
  itself once ES is back; its watermark resumes from the newest ES document,
  so an app restart doesn't miss orders either.
- **Complexity:** dual-write is ~5 lines; polling needs a worker, a watermark,
  and idempotent bulk writes.

Recovery: `python -m scripts.reindex_orders` rebuilds the whole index from
Postgres (the system of record). `GET /api/orders/{id}` reports `es_in_sync`
so staleness is visible.

## Acceptance checks

```bash
cd backend && source .venv/bin/activate
.venv/bin/pytest ../tests/test_api.py -v   # 11 API tests (seed, orders, search, sync)
```

- `GET /api/products` returns 25 active products; `?active=false` returns 26
- Checkout returns 201 with `es_synced: true` (dual-write)
- `POST /api/search/orders {"q": "Wireless"}` matches customer names and
  product titles, with revenue/status aggs
- Narrowed facets (status + price range) shrink the result set
- Status update on an order is reflected in ES and the sync badge

## Demo flow

1. Seed: `python -m scripts.seed`
2. Open `/`, pick a user, add products, checkout → order confirmation
3. Open `/admin`, search `Wireless` → see hits, KPIs
4. Open an order → change status to SHIPPED → badge stays in sync
5. In `/admin/catalog`, edit `Wireless Mouse Pro` price → order history still
   shows the old snapshot price

## Layout

```
backend/app/{api,repositories,services,workers,db}  # FastAPI app
backend/scripts/{seed,reindex_orders}.py
frontend/src/{views,api}                            # Vue 3 SPA
tests/test_api.py
docker-compose.yml
NOTES.md                                            # learning milestones
```

## Environment limitation

Docker was unavailable in the build workspace, so `docker-compose.yml` is
provided but was verified against native Postgres/Mongo/ES binaries instead.
