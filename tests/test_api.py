"""API tests against the local dev databases (Postgres, MongoDB, Elasticsearch).

Run from backend/:  .venv/bin/pytest ../tests/test_api.py -v
Note: tests insert a throwaway order; re-run `python -m scripts.seed` to reset.
"""
import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_users_list():
    r = client.get("/api/users")
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 8
    names = {u["name"] for u in users}
    assert {"John Doe", "Wendy Wireless", "Riley Brooks"} <= names


def test_products_list_hides_inactive():
    r = client.get("/api/products")
    assert r.status_code == 200
    products = r.json()
    assert len(products) >= 24
    assert all(p["active"] for p in products)
    # every product has the document-oriented fields
    p = products[0]
    assert {"sku", "title", "price", "category", "tags", "attributes", "variants"} <= set(p)
    assert isinstance(p["variants"], list) and len(p["variants"]) >= 1


def test_products_include_inactive():
    r = client.get("/api/products", params={"active": "false"})
    assert r.status_code == 200
    assert any(not p["active"] for p in r.json())


def test_products_category_filter():
    r = client.get("/api/products", params={"category": "audio"})
    assert r.status_code == 200
    products = r.json()
    assert products and all(p["category"] == "audio" for p in products)


def _wireless_mouse_pro_id() -> str:
    r = client.get("/api/products", params={"q": "Wireless Mouse Pro"})
    return r.json()[0]["id"]


def test_place_order_dual_write():
    pid = _wireless_mouse_pro_id()
    r = client.post("/api/orders", json={"user_id": 1, "items": [{"product_id": pid, "quantity": 1}]})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "PENDING"
    assert order["items"][0]["title"] == "Wireless Mouse Pro"  # current catalog snapshot
    assert order["items"][0]["unit_price"] == 59.99
    assert order["total_amount"] == 59.99
    assert order["es_synced"] is True


def test_place_order_rejects_unknown_product():
    r = client.post("/api/orders", json={"user_id": 1, "items": [{"product_id": "0" * 24, "quantity": 1}]})
    assert r.status_code == 400


def test_order_detail_snapshot_immutable():
    # Seeded order 17 contains the pre-rename snapshot.
    r = client.get("/api/orders/17")
    assert r.status_code == 200
    titles = [i["title"] for i in r.json()["items"]]
    assert "Wireless Mouse" in titles
    assert "Wireless Mouse Pro" not in titles


def test_search_omni_wireless():
    r = client.post("/api/search/orders", json={"q": "Wireless"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] > 0
    customers = {h["customer"]["name"] for h in body["hits"]}
    assert "Wendy Wireless" in customers  # name match, not just product match
    assert body["aggs"]["total_revenue"] > 0
    assert sum(b["count"] for b in body["aggs"]["by_status"]) == body["total"]


def test_search_filters_shrink_results():
    base = client.post("/api/search/orders", json={}).json()["total"]
    narrowed = client.post(
        "/api/search/orders",
        json={"statuses": ["PENDING"], "min_total": 200},
    ).json()["total"]
    assert 0 < narrowed < base


def test_search_date_range_shrinks_results():
    base = client.post("/api/search/orders", json={}).json()["total"]
    narrow = client.post(
        "/api/search/orders",
        json={"date_from": "2026-09-20", "date_to": "2026-09-26"},
    ).json()
    assert 0 < narrow["total"] < base
    assert sum(b["count"] for b in narrow["aggs"]["by_status"]) == narrow["total"]


def test_status_update_syncs_es():
    pid = _wireless_mouse_pro_id()
    order_id = client.post(
        "/api/orders", json={"user_id": 2, "items": [{"product_id": pid, "quantity": 1}]}
    ).json()["id"]
    r = client.patch(f"/api/orders/{order_id}/status", json={"status": "SHIPPED"})
    assert r.status_code == 200
    assert r.json()["status"] == "SHIPPED"
    detail = client.get(f"/api/orders/{order_id}").json()
    assert detail["es_in_sync"] is True
    hit = client.post("/api/search/orders", json={"q": "Jane Smith"}).json()["hits"]
    assert any(h["order_id"] == order_id and h["status"] == "SHIPPED" for h in hit)


# --- Celery / RabbitMQ sync strategy ---------------------------------------

import pytest

from app.core.database import es_client as _es_client
from app.core.database import mongo_db as _mongo_db
from app.core.database import pg_pool as _pg_pool
from app.repositories import es as _es_repo
from app.repositories import postgres as _pg_repo
from app.services import orders as _order_service
from app.tasks import order_sync as _order_sync


def test_celery_strategy_enqueues_only_after_commit(monkeypatch):
    """place_order with sync_strategy='celery' commits to Postgres first,
    then enqueues exactly one task carrying the committed order id."""
    enqueued = []
    monkeypatch.setattr(
        _order_sync.sync_order_to_elasticsearch, "delay",
        lambda order_id: enqueued.append(order_id),
    )
    pid = _wireless_mouse_pro_id()
    result = _order_service.place_order(
        _pg_pool(), _mongo_db(), _es_client(), "orders",
        1, [{"product_id": pid, "quantity": 1}], "celery",
    )
    assert result["es_synced"] is False  # enqueued, not yet indexed
    assert enqueued == [result["id"]]    # one task, after commit
    assert _pg_repo.get_order(_pg_pool(), result["id"]) is not None


def test_celery_task_indexes_canonical_order_idempotently():
    """The worker task reads the canonical PG row and indexes it by order id;
    running it twice does not duplicate or corrupt the document."""
    pid = _wireless_mouse_pro_id()
    order_id = client.post(
        "/api/orders", json={"user_id": 3, "items": [{"product_id": pid, "quantity": 1}]}
    ).json()["id"]
    es = _es_client()
    es.delete(index="orders", id=order_id, refresh=True)  # simulate "not yet synced"
    assert _es_repo.get_doc(es, "orders", order_id) is None

    first = _order_sync.sync_order_to_elasticsearch.run(order_id)
    assert first == {"order_id": order_id, "indexed": True}
    doc = _es_repo.get_doc(es, "orders", order_id)
    assert doc["status"] == "PENDING"
    assert doc["order_id"] == order_id

    second = _order_sync.sync_order_to_elasticsearch.run(order_id)  # redelivery
    assert second["indexed"] is True
    assert _es_repo.get_doc(es, "orders", order_id) == doc  # unchanged


def test_celery_task_skips_missing_order_without_retry_loop():
    res = _order_sync.sync_order_to_elasticsearch.run(999999999)
    assert res == {"order_id": 999999999, "indexed": False, "reason": "not_found"}


def test_celery_task_raises_on_es_failure(monkeypatch):
    """An ES outage must propagate (so Celery retries) rather than being
    swallowed; the Postgres order is untouched."""
    def _boom():
        raise ConnectionError("elasticsearch unavailable")
    monkeypatch.setattr(_order_sync, "es_client", _boom)
    with pytest.raises(ConnectionError):
        _order_sync.sync_order_to_elasticsearch.run(17)
    assert _pg_repo.get_order(_pg_pool(), 17) is not None  # PG order safe
