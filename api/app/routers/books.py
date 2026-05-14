from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import cache
from ..models import Book

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[Book], summary="Lista best-sellers")
def list_books(
    limit: int = Query(50, ge=1, le=100, description="Número máximo de livros a serem retornados"),
    offset: int = Query(0, ge=0, description="Número de livros a serem ignorados"),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_price: Optional[float] = Query(None, ge=0),
):
    """Retorne a lista atual dos mais vendidos, com filtros e paginação opcionais."""
    snap = cache.current()
    if snap is None:
        raise HTTPException(status_code=503, detail="Cache não está pronto")
    books = snap.books
    if min_rating is not None:
        books = [b for b in books if (b.rating or 0) >= min_rating]
    if max_price is not None:
        books = [b for b in books if b.price is not None and b.price <= max_price]
    return books[offset : offset + limit]


@router.get("/search", response_model=list[Book], summary="Pesquise por título ou autor")
def search_books(q: str = Query(..., min_length=2, description="Query string")):
    """Pesquisa de substring sem distinção entre maiúsculas e minúsculas sobre título e autor."""
    snap = cache.current()
    if snap is None:
        raise HTTPException(status_code=503, detail="Cache não está pronto")
    needle = q.lower()
    return [
        b for b in snap.books
        if needle in b.title.lower() or needle in (b.author or "").lower()
    ]


@router.get("/{book_id}", response_model=Book, summary="Obtenha um único livro por classificação")
def get_book(book_id: int):
    """Devolva um livro pela classificação de mais vendido (1 = topo da lista)."""
    snap = cache.current()
    if snap is None:
        raise HTTPException(status_code=503, detail="Cache não está pronto")
    for b in snap.books:
        if b.id == book_id:
            return b
    raise HTTPException(status_code=404, detail=f"Nenhum livro com classificação {book_id}")
