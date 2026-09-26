from fastapi import APIRouter

from ..core.database import pg_pool
from ..models.schemas import UserOut
from ..repositories import postgres as pg_repo

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users():
    return pg_repo.list_users(pg_pool())
