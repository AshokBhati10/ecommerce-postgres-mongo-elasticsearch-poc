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
