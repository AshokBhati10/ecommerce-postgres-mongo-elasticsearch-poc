"""Order placement: validate against MongoDB, write to Postgres in one
transaction, then synchronize to Elasticsearch per the configured strategy."""
import logging

from ..repositories import es as es_repo
from ..repositories import mongo as mongo_repo
from ..repositories import postgres as pg_repo

logger = logging.getLogger(__name__)


def place_order(pool, db, es, index: str, user_id: int,
                items: list[dict], sync_strategy: str) -> dict:
    # 1. Validate the cart against the CURRENT MongoDB catalog and take the
    #    title/price snapshot. Historical rows keep this snapshot forever.
    user = pg_repo.get_user(pool, user_id)
    if not user:
        raise ValueError(f"Unknown user_id {user_id}")
    product_ids = [i["product_id"] for i in items]
    products = mongo_repo.get_products_by_ids(db, product_ids)
    missing = [pid for pid in product_ids if pid not in products]
    if missing:
        raise ValueError(f"Unknown product_id(s): {', '.join(missing)}")
    inactive = [pid for pid in product_ids if not products[pid].get("active", True)]
    if inactive:
        raise ValueError(f"Product(s) not available: {', '.join(inactive)}")

    snapshots = [
        {
            "product_id": pid,
            "title": products[pid]["title"],
            "quantity": next(i["quantity"] for i in items if i["product_id"] == pid),
            "unit_price": products[pid]["price"],
        }
        for pid in product_ids
    ]

    # 2. PostgreSQL transaction: one orders row + N order_items rows, all or nothing.
    order = pg_repo.create_order(pool, user_id, snapshots)
    full = pg_repo.get_order(pool, order["id"])

    # 3. Elasticsearch sync.
    es_synced = False
    if sync_strategy == "dual_write":
        try:
            es_repo.index_order(es, index, full)
            es_synced = True
        except Exception as exc:  # ES down: order is safe in Postgres; polling reindex heals it.
            logger.warning("Dual-write to Elasticsearch failed for order %s: %s",
                           full["id"], exc)
    elif sync_strategy == "celery":
        # Enqueued only AFTER the Postgres transaction committed above, so the
        # worker always finds the order. es_synced stays False until the
        # worker actually indexes the document (tracked via es_in_sync).
        _enqueue_order_sync(full["id"])
    # With "polling" the background worker picks the order up within one interval.

    return {**_order_out(full), "es_synced": es_synced}


def _enqueue_order_sync(order_id: int) -> bool:
    """Publish the ES sync task to RabbitMQ. Call only after the Postgres
    transaction committed. Never raises: if the broker is unreachable the
    order remains safe in Postgres and the caller reports es_synced=False."""
    try:
        from ..tasks.order_sync import sync_order_to_elasticsearch
        sync_order_to_elasticsearch.delay(order_id)
        return True
    except Exception as exc:
        logger.warning("Could not enqueue ES sync task for order %s: %s",
                       order_id, exc)
        return False


def get_order_detail(pool, es, index: str, order_id: int) -> dict | None:
    """Canonical read from PostgreSQL + a best-effort ES sync badge."""
    order = pg_repo.get_order(pool, order_id)
    if not order:
        return None
    out = _order_out(order)
    try:
        doc = es_repo.get_doc(es, index, order_id)
        out["es_in_sync"] = bool(
            doc
            and doc.get("status") == order["status"]
            and abs(float(doc.get("total_amount", 0)) - float(order["total_amount"])) < 0.005
        )
    except Exception:
        out["es_in_sync"] = False
    return out


def update_status(pool, es, index: str, order_id: int, status: str,
                  sync_strategy: str = "dual_write") -> dict | None:
    order = pg_repo.update_order_status(pool, order_id, status)
    if not order:
        return None
    full = pg_repo.get_order(pool, order_id)
    if sync_strategy == "celery":
        _enqueue_order_sync(order_id)  # worker re-reads the committed row
    else:
        try:
            es_repo.index_order(es, index, full)  # keep Screen 3 accurate
        except Exception as exc:
            logger.warning("ES status sync failed for order %s: %s", order_id, exc)
    return _order_out(full)


def _order_out(order: dict) -> dict:
    return {
        "id": order["id"],
        "user_id": order["user_id"],
        "customer": {
            "id": order["user_id"],
            "name": order["customer_name"],
            "email": order["customer_email"],
        },
        "order_date": order["order_date"],
        "status": order["status"],
        "total_amount": float(order["total_amount"]),
        "updated_at": order["updated_at"],
        "items": [
            {
                "product_id": i["product_id"],
                "title": i["title"],
                "quantity": i["quantity"],
                "unit_price": float(i["unit_price"]),
            }
            for i in order["items"]
        ],
    }
