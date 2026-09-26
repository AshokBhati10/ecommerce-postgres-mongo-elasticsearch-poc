"""Rebuild the Elasticsearch orders index from PostgreSQL in one step.

Run from backend/:  python -m scripts.reindex_orders
"""
import sys

sys.path.insert(0, ".")

from app.core import database as db
from app.core.settings import settings
from app.services import sync as sync_service


def main():
    n = sync_service.reindex_all(db.pg_pool(), db.es_client(), settings.es_index)
    print(f"Reindexed {n} orders into '{settings.es_index}'")
    db.close_all()


if __name__ == "__main__":
    main()
