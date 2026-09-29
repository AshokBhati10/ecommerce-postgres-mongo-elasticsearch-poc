"""Elasticsearch access: the `products` index. The Storefront search/listing
path reads ONLY from here.

MongoDB remains the source of truth for the product catalog; this index is a
read-optimized copy kept in sync via bulk reindexing and the Celery product
task (see tasks/product_sync.py). It is fully separate from the orders index
(repositories/es.py) — product and order documents are never mixed.
"""
from elasticsearch import Elasticsearch

# ES refuses from+size past this per index; search_products degrades
# gracefully (empty page, accurate total) instead of letting the 400 reach
# the API.
MAX_RESULT_WINDOW = 10_000

PRODUCTS_MAPPING = {
    "mappings": {
        "properties": {
            # MongoDB _id as string; also the ES document _id.
            "id": {"type": "keyword"},
            "sku": {"type": "keyword"},
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "description": {"type": "text"},
            "category": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "price": {"type": "float"},
            "active": {"type": "boolean"},
            "image_url": {"type": "keyword"},
            "stock": {"type": "integer"},
            # Extracted for search/filtering; always strings.
            "brand": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "color": {"type": "keyword"},
            # Display-oriented free-form attributes. Mapped as `flattened`
            # (not `object`) on purpose: attribute keys are heterogeneous
            # across products (e.g. attributes.bluetooth is a boolean on one
            # catalog product and a version string on generated ones, and
            # admins free-type key:value pairs). Dynamic object mapping would
            # reject such documents at index time; flattened indexes them all
            # and still allows exact lookups like attributes.brand.
            "attributes": {"type": "flattened"},
            "variants": {"type": "object"},
            "updated_at": {"type": "date"},
        }
    }
}


def ensure_products_index(es: Elasticsearch, index: str) -> None:
    if not es.indices.exists(index=index):
        es.indices.create(index=index, body=PRODUCTS_MAPPING)


def recreate_products_index(es: Elasticsearch, index: str) -> None:
    if es.indices.exists(index=index):
        es.indices.delete(index=index)
    es.indices.create(index=index, body=PRODUCTS_MAPPING)


def product_to_doc(doc: dict) -> dict:
    """Flatten one canonical MongoDB product into an ES document.

    Carries everything the Storefront product card renders, so search
    results need no MongoDB follow-up lookups (no N+1).
    """
    attrs = doc.get("attributes", {}) or {}
    return {
        "id": str(doc["_id"]),
        "sku": doc.get("sku", ""),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "category": doc.get("category", ""),
        "tags": doc.get("tags", []),
        "price": float(doc.get("price", 0) or 0),
        "active": bool(doc.get("active", True)),
        "image_url": doc.get("image_url", ""),
        "stock": int(doc.get("stock", 0) or 0),
        "brand": str(attrs.get("brand", "") or ""),
        "color": str(attrs.get("color", "") or ""),
        "attributes": attrs,
        "variants": doc.get("variants", []),
        "updated_at": doc.get("updated_at"),
    }


def index_product(es: Elasticsearch, index: str, doc: dict) -> None:
    """Upsert one product document (idempotent: ES _id == product id).

    Takes a converted document as produced by :func:`product_to_doc`.
    """
    es.index(index=index, id=str(doc["id"]), document=doc, refresh=True)


def delete_product_doc(es: Elasticsearch, index: str, product_id: str) -> None:
    from elasticsearch import NotFoundError

    try:
        es.delete(index=index, id=product_id, refresh=True)
    except NotFoundError:
        pass  # already absent: nothing to do
    # Any other ES error propagates so the Celery task retries instead of
    # silently dropping the delete.


def bulk_index_products(es: Elasticsearch, index: str, docs: list[dict],
                        refresh: bool = True, chunk_size: int = 2000) -> int:
    """Bulk-index one batch of MongoDB product docs via the ES Bulk API.

    No per-document HTTP requests: one batch becomes a handful of bulk
    requests of `chunk_size` documents each.
    """
    from elasticsearch.helpers import bulk

    actions = [
        {
            "_index": index,
            "_id": str(d["_id"]),
            "_source": product_to_doc(d),
        }
        for d in docs
    ]
    if actions:
        bulk(es, actions, refresh=refresh, chunk_size=chunk_size)
    return len(actions)


def search_products(
    es: Elasticsearch,
    index: str,
    q: str = "",
    category: str | None = None,
    active_only: bool = True,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Customer product search: full-text query + filters + pagination, all in
    Elasticsearch. Returns {"items": [...], "total": n} with complete product
    documents (no MongoDB lookup needed to render results)."""
    must: list[dict] = []
    if q:
        must.append(
            {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "title^3",
                        "description",
                        "brand^2",
                        "tags^2",
                    ],
                }
            }
        )
    filters: list[dict] = []
    if active_only:
        filters.append({"term": {"active": True}})
    if category:
        filters.append({"term": {"category": category}})

    frm = (page - 1) * page_size
    body: dict = {
        # accurate totals even past ES's default 10k hit-count cap
        "track_total_hits": True,
        "query": {"bool": {"must": must or [{"match_all": {}}], "filter": filters}},
        "size": page_size,
        "from": frm,
    }
    if frm >= MAX_RESULT_WINDOW:
        # Past ES's result window the search would 400; report the accurate
        # total with an empty page instead (same semantic as a beyond-last
        # page). The Storefront cannot reach these pages via prev/next.
        total = es.count(index=index, body={"query": body["query"]})["count"]
        return {"items": [], "total": total}
    if q:
        # relevance first, then a stable title order for ties
        body["sort"] = ["_score", {"title.keyword": "asc"}]
    else:
        # no query: deterministic title order (mirrors the Mongo listing)
        body["sort"] = [{"title.keyword": "asc"}]
    resp = es.search(index=index, body=body)
    return {
        "items": [h["_source"] for h in resp["hits"]["hits"]],
        "total": resp["hits"]["total"]["value"],
    }


def get_product_doc(es: Elasticsearch, index: str, product_id: str) -> dict | None:
    try:
        return es.get(index=index, id=product_id)["_source"]
    except Exception:
        return None
