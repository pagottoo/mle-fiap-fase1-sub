import logging

from fastapi import APIRouter, HTTPException

from .. import cache, scraper
from ..models import RefreshResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/refresh", response_model=RefreshResponse, summary="Re-scrape Amazon e atualiza o cache")
def refresh():
    """Trigga uma raspagem nova e atualiza o cache.

    Se a Amazon bloquear ou voltar conteuado não parseavel, o cache anterior é mantido
    e um 502 é retornado então é possivel saber que o refresh não aconteceu com sucesso.
    """
    try:
        books = scraper.scrape()
    except scraper.ScrapeError as exc:
        logger.warning("Refresh falhou: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"O scrape falhou; cache não mudou. {exc}",
        ) from exc

    snap = cache.save(books, source_url=scraper.BESTSELLERS_URL)
    return RefreshResponse(
        status="ok",
        fetched_at=snap.fetched_at,
        books_fetched=snap.count,
        source="live",
    )
