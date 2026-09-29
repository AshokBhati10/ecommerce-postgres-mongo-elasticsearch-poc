import logging

from fastapi import APIRouter, HTTPException, Query

from ..core.database import es_client, mongo_db
from ..core.settings import settings
from ..models.schemas import ProductCreate, ProductOut, ProductPage, ProductUpdate
from ..repositories import es_products as es_products_repo
from ..repositories import mongo as mongo_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut] | ProductPage)
def list_products(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    # active=true (default): only active products. active=false: include inactive too.
    active: bool = Query(default=True),
    # page omitted -> legacy behavior: full MongoDB list (kept for existing
    # callers; Catalog Admin now paginates explicitly via admin=true).
    page: int | None = Query(default=None, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="items per page"),
    # admin=true + page: paginate straight from MongoDB (the source of truth)
    # for the Catalog Admin UI. The Storefront path (admin=false) reads
    # Elasticsearch instead.
    admin: bool = Query(default=False),
):
    active_filt = True if active else None
    if page is None:
        return mongo_repo.list_products(
            mongo_db(), category=category, q=q, active=active_filt
        )
    if admin:
        items, total = mongo_repo.list_products_paginated(
            mongo_db(), category=category, q=q, active=active_filt,
            page=page, page_size=page_size,
        )
        total_pages = (total + page_size - 1) // page_size if total else 0
        return ProductPage(
            items=items, page=page, page_size=page_size,
            total=total, total_pages=total_pages,
        )
    # Storefront search/listing path: Elasticsearch performs the search,
    # category filtering, and pagination. MongoDB is NOT queried here — it
    # remains the source of truth, ES is the read/search layer.
    result = es_products_repo.search_products(
        es_client(), settings.es_products_index,
        q=q or "", category=category, active_only=active,
        page=page, page_size=page_size,
    )
    total = result["total"]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return ProductPage(
        items=result["items"], page=page, page_size=page_size,
        total=total, total_pages=total_pages,
    )


@router.get("/categories", response_model=list[str])
def list_categories():
    return mongo_repo.distinct_categories(mongo_db())


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    product = mongo_repo.get_product(mongo_db(), product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate):
    product = mongo_repo.create_product(mongo_db(), payload.model_dump())
    # MongoDB is the source of truth: the write above already succeeded.
    # The ES document syncs asynchronously via the existing Celery/RabbitMQ
    # infrastructure; if the broker is down the catalog is still correct.
    _enqueue_product_sync(product["id"])
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductUpdate):
    product = mongo_repo.update_product(
        mongo_db(), product_id, payload.model_dump(exclude_unset=True)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    _enqueue_product_sync(product["id"])
    return product


def _enqueue_product_sync(product_id: str) -> bool:
    """Publish the product ES sync task to RabbitMQ. Call only after the
    MongoDB write succeeded. Never raises: if the broker is unreachable the
    product remains safe in MongoDB and the caller is unaffected."""
    try:
        from ..tasks.product_sync import sync_product_to_elasticsearch
        sync_product_to_elasticsearch.delay(product_id)
        return True
    except Exception as exc:
        logger.warning("Could not enqueue ES sync task for product %s: %s",
                       product_id, exc)
        return False
