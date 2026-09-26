from fastapi import APIRouter

from ..core.database import es_client
from ..core.settings import settings
from ..models.schemas import SearchRequest
from ..repositories import es as es_repo

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/orders")
def search_orders(payload: SearchRequest):
    # Screen 3 reads from Elasticsearch ONLY — never Postgres or MongoDB.
    return es_repo.search_orders(
        es_client(),
        settings.es_index,
        q=payload.q,
        statuses=payload.statuses or None,
        date_from=payload.date_from,
        date_to=payload.date_to,
        min_total=payload.min_total,
        max_total=payload.max_total,
        size=payload.size,
    )
