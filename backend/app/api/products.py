from fastapi import APIRouter, HTTPException, Query

from ..core.database import mongo_db
from ..models.schemas import ProductCreate, ProductOut, ProductUpdate
from ..repositories import mongo as mongo_repo

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
    active: bool = Query(default=True),
):
    return mongo_repo.list_products(mongo_db(), category=category, q=q, active=active)


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
    return mongo_repo.create_product(mongo_db(), payload.model_dump())


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductUpdate):
    product = mongo_repo.update_product(
        mongo_db(), product_id, payload.model_dump(exclude_unset=True)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
