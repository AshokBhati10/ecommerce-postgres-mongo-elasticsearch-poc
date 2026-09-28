"""Celery task: sync one canonical PostgreSQL order into Elasticsearch.

Enqueued by the API *after* the Postgres order transaction has committed
(see services/orders.py). The task carries only the order id; the worker
reads the canonical row from PostgreSQL and indexes it with the order id as
the Elasticsearch document id, so re-running the task is idempotent.

Transient Elasticsearch failures raise and are retried with backoff;
PostgreSQL stays the source of truth regardless.
"""
import logging

from ..celery_app import celery_app
from ..core.database import es_client, pg_pool
from ..core.settings import settings
from ..repositories import es as es_repo
from ..repositories import postgres as pg_repo

logger = logging.getLogger(__name__)


@celery_app.task(
    name="orders.sync_order_to_elasticsearch",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=5,
    retry_backoff=5,      # 5s, 10s, 20s, ... (plus jitter)
    retry_backoff_max=300,
    retry_jitter=True,
)
def sync_order_to_elasticsearch(self, order_id: int) -> dict:
    order = pg_repo.get_order(pg_pool(), order_id)
    if order is None:
        # The order does not exist (e.g. rolled back): nothing to index.
        # Return instead of raising so this is not retried forever.
        logger.warning("Order %s not found in PostgreSQL; skipping ES sync", order_id)
        return {"order_id": order_id, "indexed": False, "reason": "not_found"}
    es = es_client()
    es_repo.ensure_index(es, settings.es_index)
    # Idempotent: document id == order id, so a redelivered task overwrites
    # the same document instead of creating a duplicate.
    es_repo.index_order(es, settings.es_index, order)
    logger.info("Indexed order %s into Elasticsearch", order_id)
    return {"order_id": order_id, "indexed": True}
