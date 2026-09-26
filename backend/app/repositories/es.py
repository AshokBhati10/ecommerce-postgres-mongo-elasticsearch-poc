"""Elasticsearch access: the `orders` index. Screen 3 reads ONLY from here."""
from datetime import datetime

from elasticsearch import Elasticsearch

ORDERS_MAPPING = {
    "mappings": {
        "properties": {
            "order_id": {"type": "integer"},
            "order_date": {"type": "date"},
            "status": {"type": "keyword"},
            "total_amount": {"type": "float"},
            "updated_at": {"type": "date"},
            "customer": {
                "properties": {
                    "id": {"type": "integer"},
                    "name": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "email": {"type": "keyword"},
                }
            },
            "items": {
                "properties": {
                    "product_id": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                    "quantity": {"type": "integer"},
                    "unit_price": {"type": "float"},
                }
            },
        }
    }
}


def ensure_index(es: Elasticsearch, index: str) -> None:
    if not es.indices.exists(index=index):
        es.indices.create(index=index, body=ORDERS_MAPPING)


def recreate_index(es: Elasticsearch, index: str) -> None:
    if es.indices.exists(index=index):
        es.indices.delete(index=index)
    es.indices.create(index=index, body=ORDERS_MAPPING)


def order_to_doc(order: dict) -> dict:
    """Flatten one Postgres order (with items + customer) into an ES document."""
    return {
        "order_id": order["id"],
        "order_date": order["order_date"],
        "status": order["status"],
        "total_amount": float(order["total_amount"]),
        "updated_at": order["updated_at"],
        "customer": {
            "id": order["user_id"],
            "name": order["customer_name"],
            "email": order["customer_email"],
        },
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


def index_order(es: Elasticsearch, index: str, order: dict) -> None:
    es.index(index=index, id=order["id"], document=order_to_doc(order), refresh=True)


def bulk_index_orders(es: Elasticsearch, index: str, orders: list[dict]) -> None:
    from elasticsearch.helpers import bulk

    actions = [
        {
            "_index": index,
            "_id": o["id"],
            "_source": order_to_doc(o),
        }
        for o in orders
    ]
    if actions:
        bulk(es, actions, refresh=True)


def get_doc(es: Elasticsearch, index: str, order_id: int) -> dict | None:
    try:
        return es.get(index=index, id=order_id)["_source"]
    except Exception:
        return None


def max_updated_at(es: Elasticsearch, index: str) -> datetime | None:
    """Newest updated_at in the index, so the polling worker resumes where ES
    left off instead of missing orders changed while the app was down."""
    try:
        res = es.search(index=index, size=0,
                        aggs={"max_updated": {"max": {"field": "updated_at"}}})
        val = (res.get("aggregations") or {}).get("max_updated", {}).get("value_as_string")
        return datetime.fromisoformat(val) if val else None
    except Exception:
        return None


def search_orders(
    es: Elasticsearch,
    index: str,
    q: str = "",
    statuses: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    min_total: float | None = None,
    max_total: float | None = None,
    size: int = 50,
) -> dict:
    must: list[dict] = []
    if q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": ["customer.name^2", "items.title", "customer.email"],
                }
            }
        )
    filters: list[dict] = []
    if statuses:
        filters.append({"terms": {"status": statuses}})
    if date_from or date_to:
        rng: dict = {}
        if date_from:
            rng["gte"] = date_from
        if date_to:
            rng["lte"] = date_to
        filters.append({"range": {"order_date": rng}})
    if min_total is not None or max_total is not None:
        rng = {}
        if min_total is not None:
            rng["gte"] = min_total
        if max_total is not None:
            rng["lte"] = max_total
        filters.append({"range": {"total_amount": rng}})

    body: dict = {
        "query": {"bool": {"must": must or [{"match_all": {}}], "filter": filters}},
        "aggs": {
            "total_revenue": {"sum": {"field": "total_amount"}},
            "by_status": {"terms": {"field": "status"}},
        },
        "sort": [{"order_date": {"order": "desc"}}],
        "size": size,
    }
    resp = es.search(index=index, body=body)
    hits = [h["_source"] for h in resp["hits"]["hits"]]
    aggs = resp.get("aggregations", {})
    return {
        "total": resp["hits"]["total"]["value"],
        "hits": hits,
        "aggs": {
            "total_revenue": round(aggs.get("total_revenue", {}).get("value") or 0, 2),
            "by_status": [
                {"status": b["key"], "count": b["doc_count"]}
                for b in aggs.get("by_status", {}).get("buckets", [])
            ],
        },
    }
