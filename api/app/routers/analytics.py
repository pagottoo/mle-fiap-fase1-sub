from fastapi import APIRouter, HTTPException, Query

from .. import analytics, cache
from ..models import AuthorCount, Book, Overview, PriceBucket

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_snapshot():
    snap = cache.current()
    if snap is None:
        raise HTTPException(status_code=503, detail="Cache não está pronto")
    return snap


@router.get("/overview", response_model=Overview, summary="High-level KPIs")
def get_overview():
    return analytics.overview(_require_snapshot())


@router.get("/top-rated", response_model=list[Book], summary="Top N best-rated")
def get_top_rated(limit: int = Query(10, ge=1, le=50)):
    return analytics.top_rated(_require_snapshot().books, limit=limit)


@router.get("/by-author", response_model=list[AuthorCount], summary="Livros agrupados por autor")
def get_by_author():
    return analytics.by_author(_require_snapshot().books)


@router.get("/price-ranges", response_model=list[PriceBucket], summary="Distribuição de livros por faixas de preço")
def get_price_ranges():
    return analytics.price_ranges(_require_snapshot().books)
