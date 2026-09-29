"""Elasticsearch synchronization strategies.

Strategy A — Dual-write: the API indexes the ES document immediately after the
Postgres commit (see services/orders.py). If ES is down, the order is still
safe in Postgres and the polling worker (or a manual reindex) heals it.

Strategy B — Periodic polling: a background thread wakes every
POLL_INTERVAL_SECONDS, asks Postgres for orders changed since its last run,
and bulk-indexes them into Elasticsearch.

scripts/reindex_orders.py rebuilds the whole orders index from Postgres in one
step; scripts/reindex_products.py rebuilds the products index from MongoDB.
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from ..repositories import es as es_repo
from ..repositories import es_products as es_products_repo
from ..repositories import postgres as pg_repo

logger = logging.getLogger(__name__)


def reindex_all(pool, es, index: str) -> int:
    """Drop + recreate the index and bulk-load every Postgres order.

    Reads and indexes in batches so a 50k-order reindex is ~50 statements
    and ~100 bulk HTTP requests instead of 50k per-order item queries and
    50k individual index requests.
    """
    es_repo.recreate_index(es, index)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    total = 0
    for batch in pg_repo.iter_orders_with_items(pool, epoch):
        es_repo.bulk_index_orders(es, index, batch)
        total += len(batch)
    logger.info("Reindexed %d orders into %s", total, index)
    return total


def reindex_all_products(mdb, es, index: str, batch_size: int = 5000) -> int:
    """Drop + recreate the products index and bulk-load every MongoDB product.

    Reads MongoDB in batches and uses the Elasticsearch Bulk API (no
    per-document HTTP requests); refreshes the index once at the end instead
    of per batch. Never touches the orders index.
    """
    es_products_repo.recreate_products_index(es, index)
    total = 0
    batch: list[dict] = []
    for doc in mdb.products.find({}, batch_size=batch_size):
        batch.append(doc)
        if len(batch) >= batch_size:
            es_products_repo.bulk_index_products(es, index, batch, refresh=False)
            total += len(batch)
            batch = []
    if batch:
        es_products_repo.bulk_index_products(es, index, batch, refresh=False)
        total += len(batch)
    es.indices.refresh(index=index)
    logger.info("Reindexed %d products into %s", total, index)
    return total


def sync_changed_since(pool, es, index: str, since: datetime) -> tuple[int, datetime]:
    """Index orders changed after `since`. Returns (count, new_high_watermark)."""
    orders = pg_repo.get_changed_orders(pool, since)
    if orders:
        es_repo.bulk_index_orders(es, index, orders)
        since = max(o["updated_at"] for o in orders)
    return len(orders), since


def start_polling_worker(pool, es, index: str, interval: int,
                         stop_event: threading.Event) -> threading.Thread:
    """Background thread: poll Postgres for changed orders and bulk-sync to ES."""

    def _run() -> None:
        # Resume where ES left off (not "now"), with a small overlap: orders
        # changed while the app was down are caught on the first poll.
        # Re-indexing is idempotent (same _id), so the overlap is safe.
        resume = es_repo.max_updated_at(es, index)
        watermark = (resume - timedelta(seconds=60)) if resume else datetime(
            1970, 1, 1, tzinfo=timezone.utc)
        logger.info("Polling sync worker started (every %ds) for index %s",
                    interval, index)
        while not stop_event.wait(interval):
            try:
                count, watermark = sync_changed_since(pool, es, index, watermark)
                if count:
                    logger.info("Polling sync indexed %d changed order(s)", count)
            except Exception as exc:
                logger.warning("Polling sync run failed: %s", exc)

    thread = threading.Thread(target=_run, name="es-polling-sync", daemon=True)
    thread.start()
    return thread
