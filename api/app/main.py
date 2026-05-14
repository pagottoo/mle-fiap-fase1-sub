"""FastAPI entrypoint para a Amazon Best Sellers API.

FIAP MLET — Prova Substitutiva Fase 1.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from . import cache
from .models import HealthResponse
from .routers import admin, analytics, books

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    snap = cache.load()
    if snap is None:
        logger.warning("Iniciando com o cache vazio — POST /admin/refresh")
    else:
        logger.info("Cache pronto: %d livros buscados em %s", snap.count, snap.fetched_at)
    yield


app = FastAPI(
    title="Amazon Best Sellers API",
    description=(
        "REST API que expõe a lista de **best sellers em livros da Amazon** "
        "(nome, autor, avaliação, preço) e fornece visões analíticas sobre o "
        "catálogo coletado.\n\n"
        "Entrega da **Atividade Substitutiva — Fase 1** do MBA em Machine Learning "
        "Engineering (FIAP) - Thiago Pagotto - RM361741.\n\n"
        "**Fonte:** https://www.amazon.com/gp/bestsellers/books/  \n"
        "**Estratégia:** o scraper roda sob demanda via `POST /admin/refresh` e "
        "persiste um snapshot em cache; a API serve sempre a partir do cache para "
        "permanecer disponível mesmo quando a Amazon bloqueia o scraping."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(books.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["meta"], summary="Liveness probe")
def health():
    snap = cache.current()
    return HealthResponse(
        status="ok",
        fetched_at=snap.fetched_at if snap else None,
        books_in_cache=snap.count if snap else 0,
    )
