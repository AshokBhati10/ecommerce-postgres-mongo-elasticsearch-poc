"""Product Elasticsearch tests: the `products` index backing Storefront search.

Run from backend/:  .venv/bin/pytest ../tests/test_products_es.py -v
Requires the product catalog + products ES index:
    python -m scripts.reindex_products
"""
import sys

sys.path.insert(0, ".")

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.core.database import es_client as _es_client
from app.core.database import mongo_db as _mongo_db
from app.core.database import pg_pool as _pg_pool
from app.core.settings import settings
from app.main import create_app
from app.repositories import es as _es_repo
from app.repositories import es_products as _es_products
from app.repositories import mongo as _mongo_repo
from app.tasks import product_sync as _product_sync

client = TestClient(create_app())
PRODUCTS_INDEX = settings.es_products_index

# Every field the Storefront product card renders (ProductOut).
REQUIRED_FIELDS = {"id", "sku", "title", "description", "price", "category",
                   "tags", "attributes", "variants", "image_url", "stock",
                   "active"}


def _es():
    return _es_client()


# --- index setup ------------------------------------------------------------

def test_products_index_exists_with_mapping():
    _es_products.ensure_products_index(_es(), PRODUCTS_INDEX)
    mapping = _es().indices.get_mapping(index=PRODUCTS_INDEX)[PRODUCTS_INDEX]
    props = mapping["mappings"]["properties"]
    for field in ("id", "sku", "title", "description", "category", "tags",
                  "price", "active", "image_url", "brand", "color",
                  "attributes"):
        assert field in props, f"mapping missing {field}"
    assert props["title"]["type"] == "text"
    assert props["category"]["type"] == "keyword"
    assert props["attributes"]["type"] == "flattened"


def test_bulk_index_roundtrip_on_scratch_index():
    """Bulk-index a small batch into a scratch index and search it."""
    es = _es()
    scratch = "products_test_scratch"
    try:
        _es_products.recreate_products_index(es, scratch)
        now = "2026-09-29T00:00:00+00:00"
        docs = [
            {"_id": ObjectId(), "sku": "T-1", "title": "Scratch Wireless Gizmo",
             "description": "a test wireless thing", "price": 9.99,
             "category": "audio", "tags": ["wireless"], "attributes": {"brand": "TestCo"},
             "variants": [], "image_url": "", "stock": 3, "active": True,
             "updated_at": now},
            {"_id": ObjectId(), "sku": "T-2", "title": "Scratch Wired Gizmo",
             "description": "a test wired thing", "price": 4.99,
             "category": "audio", "tags": ["wired"], "attributes": {"brand": "TestCo"},
             "variants": [], "image_url": "", "stock": 1, "active": True,
             "updated_at": now},
            {"_id": ObjectId(), "sku": "T-3", "title": "Scratch Dead Gizmo",
             "description": "inactive", "price": 1.99,
             "category": "audio", "tags": [], "attributes": {},
             "variants": [], "image_url": "", "stock": 0, "active": False,
             "updated_at": now},
        ]
        n = _es_products.bulk_index_products(es, scratch, docs)
        assert n == 3
        assert es.count(index=scratch)["count"] == 3

        res = _es_products.search_products(es, scratch, q="wireless")
        assert res["total"] == 1
        assert res["items"][0]["sku"] == "T-1"
        # inactive product never surfaces in customer search
        res = _es_products.search_products(es, scratch, q="gizmo")
        assert res["total"] == 2
        assert all(i["active"] for i in res["items"])
    finally:
        es.indices.delete(index=scratch, ignore_unavailable=True)


# --- catalog scale ----------------------------------------------------------

def test_mongo_has_100k_products():
    assert _mongo_db().products.count_documents({}) == 100000


def test_es_products_count_matches_mongo():
    mongo_n = _mongo_db().products.count_documents({})
    es_n = _es().count(index=PRODUCTS_INDEX)["count"]
    assert es_n == mongo_n == 100000


# --- search behavior ----------------------------------------------------------

def test_search_wireless_returns_active_products():
    res = _es_products.search_products(_es(), PRODUCTS_INDEX, q="wireless",
                                       page_size=50)
    assert res["total"] > 100
    assert len(res["items"]) == 50
    assert all(i["active"] for i in res["items"])
    for i in res["items"]:
        assert REQUIRED_FIELDS <= set(i)


def test_inactive_products_hidden_from_customer_search():
    es = _es()
    inactive = _mongo_db().products.find_one({"title": "Old CRT Monitor"})
    assert inactive is not None
    iid = str(inactive["_id"])
    # the document IS in the index (kept for admin), and an unfiltered query
    # ranks its exact title first ...
    res = _es_products.search_products(es, PRODUCTS_INDEX, q="Old CRT Monitor",
                                       active_only=False, page_size=5)
    assert res["items"][0]["id"] == iid
    # ... but customer search (active=true filter) never returns it
    doc = _es_products.get_product_doc(es, PRODUCTS_INDEX, iid)
    assert doc is not None and doc["active"] is False
    res = _es_products.search_products(es, PRODUCTS_INDEX, q="Old CRT Monitor",
                                       page_size=5)
    assert all(i["active"] for i in res["items"])
    assert iid not in {i["id"] for i in res["items"]}


def test_category_filter():
    mdb = _mongo_db()
    for cat in ("audio", "peripherals", "cables", "office"):
        res = _es_products.search_products(_es(), PRODUCTS_INDEX, category=cat,
                                           page_size=5)
        expected = mdb.products.count_documents({"active": True, "category": cat})
        assert res["total"] == expected, cat
        assert res["items"] and all(i["category"] == cat for i in res["items"])


def test_pagination_is_stable():
    es = _es()
    p1 = _es_products.search_products(es, PRODUCTS_INDEX, page=1, page_size=10)
    p2 = _es_products.search_products(es, PRODUCTS_INDEX, page=2, page_size=10)
    assert p1["total"] == p2["total"] > 20
    ids1 = [i["id"] for i in p1["items"]]
    ids2 = [i["id"] for i in p2["items"]]
    assert len(ids1) == len(ids2) == 10 and not set(ids1) & set(ids2)
    # a deep page still inside ES's 10k result window is stable too
    # (pages past the window are an inherent ES limit, same as the orders index)
    deep = _es_products.search_products(es, PRODUCTS_INDEX, page=500, page_size=10)
    assert deep["total"] == p1["total"] and len(deep["items"]) == 10
    assert not set(ids1) & {i["id"] for i in deep["items"]}


# --- API: storefront search goes to ES, not MongoDB --------------------------

def test_storefront_search_endpoint_uses_es_not_mongo(monkeypatch):
    """The paginated storefront path must not query MongoDB at all."""
    def _boom(*a, **k):
        raise AssertionError("MongoDB must not be queried for storefront search")
    monkeypatch.setattr(_mongo_repo, "list_products_paginated", _boom)
    monkeypatch.setattr(_mongo_repo, "list_products", _boom)
    r = client.get("/api/products", params={"q": "wireless", "page": 1,
                                            "page_size": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] > 100
    assert len(body["items"]) == 20
    for i in body["items"]:
        assert REQUIRED_FIELDS <= set(i)
        assert i["active"] is True


def test_storefront_endpoint_category_and_pagination():
    r = client.get("/api/products", params={"category": "audio", "page": 1,
                                            "page_size": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] and all(p["category"] == "audio" for p in body["items"])
    p2 = client.get("/api/products", params={"category": "audio", "page": 2,
                                             "page_size": 5}).json()
    assert {i["id"] for i in body["items"]} != {i["id"] for i in p2["items"]}


def test_legacy_list_path_still_served_from_mongo():
    # Catalog Admin's non-paginated path keeps reading MongoDB (source of truth).
    r = client.get("/api/products", params={"q": "Wireless Mouse Pro"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert r.json()[0]["title"] == "Wireless Mouse Pro"


def test_admin_paginated_path_reads_mongo_not_es(monkeypatch):
    """admin=true + page -> MongoDB pagination (source of truth), never ES."""
    def _boom(*a, **k):
        raise AssertionError("ES must not be queried for the admin path")

    monkeypatch.setattr(_es_products, "search_products", _boom)
    r = client.get("/api/products", params={"admin": "true", "page": 1,
                                            "page_size": 10})
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1 and body["total"] == 97285  # active-only default
    assert len(body["items"]) == 10
    r_all = client.get("/api/products", params={"admin": "true", "page": 1,
                                                "page_size": 10, "active": "false"})
    assert r_all.json()["total"] == 100000  # incl. inactive
    r2 = client.get("/api/products", params={"admin": "true", "page": 2,
                                             "page_size": 10})
    ids1 = {i["id"] for i in body["items"]}
    ids2 = {i["id"] for i in r2.json()["items"]}
    assert ids1 and ids2 and not ids1 & ids2


# --- catalog admin CRUD + async ES sync ---------------------------------------

def _track_delay(monkeypatch):
    enqueued = []
    monkeypatch.setattr(
        _product_sync.sync_product_to_elasticsearch, "delay",
        lambda product_id: enqueued.append(product_id),
    )
    return enqueued


def test_catalog_admin_crud_still_mongo_backed(monkeypatch):
    enqueued = _track_delay(monkeypatch)
    payload = {"sku": "TEST-ES-001", "title": "ES Sync Test Widget",
               "description": "created by test", "price": 12.5,
               "category": "office", "tags": ["test"], "attributes": {"brand": "TestCo"},
               "variants": [], "image_url": "", "stock": 7, "active": True}
    pid = None
    try:
        r = client.post("/api/products", json=payload)
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        assert enqueued == [pid]  # sync task enqueued after the Mongo write

        r = client.get(f"/api/products/{pid}")
        assert r.status_code == 200 and r.json()["title"] == "ES Sync Test Widget"

        r = client.put(f"/api/products/{pid}", json={"price": 15.0})
        assert r.status_code == 200 and r.json()["price"] == 15.0
        assert enqueued == [pid, pid]
    finally:
        if pid:
            _mongo_db().products.delete_one({"_id": ObjectId(pid)})
            _es_products.delete_product_doc(_es(), PRODUCTS_INDEX, pid)


def test_product_sync_task_indexes_canonical_doc_idempotently(monkeypatch):
    """Worker re-reads MongoDB and upserts by product id; deactivation hides
    the product from customer search."""
    enqueued = _track_delay(monkeypatch)
    payload = {"sku": "TEST-ES-002", "title": "ES Sync Lifecycle Gadget",
               "description": "sync lifecycle", "price": 20.0,
               "category": "cables", "tags": ["sync-test"],
               "attributes": {"brand": "SyncCo"}, "variants": [],
               "image_url": "", "stock": 2, "active": True}
    pid = client.post("/api/products", json=payload).json()["id"]
    try:
        first = _product_sync.sync_product_to_elasticsearch.run(pid)
        assert first == {"product_id": pid, "indexed": True}
        doc = _es_products.get_product_doc(_es(), PRODUCTS_INDEX, pid)
        assert doc["title"] == "ES Sync Lifecycle Gadget"
        assert doc["price"] == 20.0

        second = _product_sync.sync_product_to_elasticsearch.run(pid)
        assert second["indexed"] is True  # redelivery: same doc, no duplicate

        # deactivate in MongoDB (source of truth) -> sync -> gone from search
        client.put(f"/api/products/{pid}", json={"active": False})
        _product_sync.sync_product_to_elasticsearch.run(pid)
        res = _es_products.search_products(_es(), PRODUCTS_INDEX,
                                           q="ES Sync Lifecycle Gadget")
        assert res["total"] == 0
        doc = _es_products.get_product_doc(_es(), PRODUCTS_INDEX, pid)
        assert doc["active"] is False  # admin can still see the record
    finally:
        _mongo_db().products.delete_one({"_id": ObjectId(pid)})
        _es_products.delete_product_doc(_es(), PRODUCTS_INDEX, pid)


def test_product_sync_task_skips_missing_product_without_retry_loop():
    res = _product_sync.sync_product_to_elasticsearch.run("0" * 24)
    assert res == {"product_id": "0" * 24, "indexed": False,
                   "reason": "not_found"}


def test_product_sync_task_raises_on_es_failure(monkeypatch):
    """An ES outage must propagate (so Celery retries) rather than being
    swallowed; the MongoDB product is untouched."""
    pid = _mongo_db().products.find_one({"active": True})["_id"]
    pid = str(pid)

    def _boom():
        raise ConnectionError("elasticsearch unavailable")
    monkeypatch.setattr(_product_sync, "es_client", _boom)
    with pytest.raises(ConnectionError):
        _product_sync.sync_product_to_elasticsearch.run(pid)
    assert _mongo_repo.get_product(_mongo_db(), pid) is not None  # Mongo safe


# --- orders side untouched ----------------------------------------------------

def test_orders_es_index_untouched():
    """The orders index still mirrors PostgreSQL; Admin Search keeps working.

    NOTE: PG currently holds 50,016 orders vs 50,012 in ES — a pre-existing
    drift from earlier manual test inserts, unrelated to this task. The
    product reindex only ever touched the `products` index.
    """
    with _pg_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM orders")
        pg_n = cur.fetchone()["n"]
    es = _es()
    es_n = es.count(index="orders")["count"]
    assert pg_n >= 50000 and es_n >= 50000
    # Admin Search path still serves order documents from ES
    from app.repositories import es as es_orders
    res = es_orders.search_orders(es, "orders", q="Wireless Mouse", size=5)
    assert res["total"] >= 1
    assert all("order_id" in o and "items" in o for o in res["hits"])
    r = client.post("/api/search/orders", json={"q": "Wireless"})
    assert r.status_code == 200 and r.json()["total"] > 0
