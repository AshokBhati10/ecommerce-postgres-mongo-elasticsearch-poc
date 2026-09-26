import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import orders, products, search, users
from .core.database import close_all, es_client, pg_pool
from .core.settings import settings
from .repositories import es as es_repo
from .services import sync as sync_service

logger = logging.getLogger(__name__)
_stop_event = threading.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up clients and make sure the orders index exists.
    pg_pool()
    es = es_client()
    try:
        es_repo.ensure_index(es, settings.es_index)
    except Exception as exc:
        logger.warning("Could not ensure ES index on startup: %s", exc)
    worker = None
    if settings.sync_strategy == "polling":
        worker = sync_service.start_polling_worker(
            pg_pool(), es, settings.es_index, settings.poll_interval_seconds, _stop_event
        )
    yield
    _stop_event.set()
    if worker:
        worker.join(timeout=5)
    close_all()


def create_app() -> FastAPI:
    app = FastAPI(title="E-Commerce Polyglot POC", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            settings.vite_api_url,
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(users.router)
    app.include_router(products.router)
    app.include_router(orders.router)
    app.include_router(search.router)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "sync_strategy": settings.sync_strategy}

    return app


app = create_app()
