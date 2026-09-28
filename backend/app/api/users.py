from fastapi import APIRouter, Query

from ..core.database import pg_pool
from ..models.schemas import UserOut
from ..repositories import postgres as pg_repo

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users():
    return pg_repo.list_users(pg_pool())


@router.get("/{user_id}/orders")
def list_user_orders(user_id: int, limit: int = Query(100, ge=1, le=500)):
    # PostgreSQL is the source of truth for orders.
    return pg_repo.list_orders_by_user(pg_pool(), user_id, limit)
