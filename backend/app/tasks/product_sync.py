"""Celery task: sync one canonical MongoDB product into the Elasticsearch
products index.

Enqueued by the products API *after* the MongoDB write has succeeded
(see api/products.py). The task carries only the product id; the worker
re-reads the canonical document from MongoDB and upserts it with the Mongo
_id as the Elasticsearch document id, so re-running the task is idempotent.

Transient Elasticsearch failures raise and are retried with backoff;
MongoDB stays the source of truth regardless. This reuses the existing
RabbitMQ/Celery infrastructure (same broker, same queue as the order sync).
"""
import logging

from ..celery_app import celery_app
from ..core.database import es_client, mongo_db
from ..core.settings import settings
from ..repositories import es_products as es_products_repo
from ..repositories import mongo as mongo_repo

logger = logging.getLogger(__name__)


@celery_app.task(
    name="products.sync_product_to_elasticsearch",
    bind=True,
    autoretry_for=(Exception,),
    max_retries=5,
    retry_backoff=5,      # 5s, 10s, 20s, ... (plus jitter)
    retry_backoff_max=300,
    retry_jitter=True,
)
def sync_product_to_elasticsearch(self, product_id: str) -> dict:
    doc = mongo_repo.get_product(mongo_db(), product_id)
    es = es_client()
    es_products_repo.ensure_products_index(es, settings.es_products_index)
    if doc is None:
        # The product no longer exists in MongoDB: drop it from the search
        # index too so it can never surface in customer search. Return
        # instead of raising so this is not retried forever.
        es_products_repo.delete_product_doc(
            es, settings.es_products_index, product_id)
        logger.warning("Product %s not found in MongoDB; removed from ES index",
                       product_id)
        return {"product_id": product_id, "indexed": False, "reason": "not_found"}
    # Idempotent: document id == Mongo _id, so a redelivered task overwrites
    # the same document instead of creating a duplicate.
    es_products_repo.index_product(es, settings.es_products_index, doc)
    logger.info("Indexed product %s into Elasticsearch", product_id)
    return {"product_id": product_id, "indexed": True}
