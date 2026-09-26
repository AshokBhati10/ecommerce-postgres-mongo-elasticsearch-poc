from fastapi import APIRouter, HTTPException

from ..core.database import es_client, mongo_db, pg_pool
from ..core.settings import settings
from ..models.schemas import OrderCreate, OrderOut, OrderPlacedOut, StatusUpdate
from ..services import orders as order_service

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderPlacedOut, status_code=201)
def place_order(payload: OrderCreate):
    try:
        return order_service.place_order(
            pg_pool(),
            mongo_db(),
            es_client(),
            settings.es_index,
            payload.user_id,
            [i.model_dump() for i in payload.items],
            settings.sync_strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{order_id}")
def get_order(order_id: int):
    order = order_service.get_order_detail(
        pg_pool(), es_client(), settings.es_index, order_id
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(order_id: int, payload: StatusUpdate):
    order = order_service.update_status(
        pg_pool(), es_client(), settings.es_index, order_id, payload.status
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
