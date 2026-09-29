"""Rebuild the product catalog in MongoDB (100k products) and the
Elasticsearch products index — without touching anything else.

- MongoDB `products` collection: dropped and rebuilt deterministically
  (hand-written catalog + inactive fixture + 100k-scale generated products),
  inserted with chunked bulk inserts (no per-document requests).
- Elasticsearch `products` index: dropped, recreated, and bulk-indexed from
  MongoDB in batches (Bulk API, no per-document requests).

Does NOT touch PostgreSQL (users/orders/order_items) or the Elasticsearch
orders index.

Run from backend/:  python -m scripts.reindex_products
"""
import sys
import time

sys.path.insert(0, ".")

from app.core import database as db
from app.core.settings import settings
from app.services import sync as sync_service
from scripts import seed as seed_mod


def main():
    t0 = time.time()
    mdb, es = db.mongo_db(), db.es_client()

    seed_mod.seed_mongo(mdb)
    seed_mod.rename_fixture(mdb)  # catalog moves on; order history does not

    n = sync_service.reindex_all_products(mdb, es, settings.es_products_index)

    mongo_count = mdb.products.count_documents({})
    es_count = es.count(index=settings.es_products_index)["count"]
    dt = time.time() - t0
    print(f"MongoDB products: {mongo_count}")
    print(f"Elasticsearch '{settings.es_products_index}' docs: {es_count}")
    print(f"Done in {dt:.1f}s")
    assert mongo_count == seed_mod.CATALOG_TARGET_TOTAL, \
        f"MongoDB has {mongo_count} products, expected {seed_mod.CATALOG_TARGET_TOTAL}"
    assert es_count == mongo_count, \
        f"ES products docs {es_count} != MongoDB products {mongo_count}"
    db.close_all()


if __name__ == "__main__":
    main()
