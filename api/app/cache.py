"""JSON-file para cache.

A api serve os dados através do cache, caso a Amazon bloquear, ou não responder ao scrap
O cache é populado na inicialização e atualizado por demanda atraves do endpoint: /admin/refresh
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Book, Snapshot

logger = logging.getLogger(__name__)

_PKG_DATA = Path(__file__).parent / "data"
DATA_DIR = Path(os.getenv("DATA_DIR", _PKG_DATA))
CACHE_FILE = DATA_DIR / "cache.json"
# O seed acompanha a imagem (não o volume). Quando DATA_DIR aponta para
# um PVC vazio, o seed em _PKG_DATA garante que a API já sobe respondendo.
SEED_FILE = _PKG_DATA / "seed.json"

_lock = threading.Lock()
_snapshot: Optional[Snapshot] = None


def _ensure_cache_file() -> None:
    """Garante que CACHE_FILE existe, copiando do seed se necessário.

    Nunca propaga exceção: se DATA_DIR não for gravável (PVC sem permissão,
    disco cheio, etc.), retorna silencioso. O load() detecta e cai pro seed
    em memória para que o pod fique up mesmo com volume mal configurado.
    """
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not CACHE_FILE.exists() and SEED_FILE.exists():
            shutil.copy(SEED_FILE, CACHE_FILE)
            logger.info("Cache populado a partir de %s -> %s", SEED_FILE, CACHE_FILE)
    except OSError as exc:
        logger.warning(
            "Não foi possível inicializar DATA_DIR=%s (%s). "
            "API vai operar com o seed em memória até a permissão ser corrigida.",
            DATA_DIR, exc,
        )


def _load_file(path: Path) -> Optional[Snapshot]:
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return Snapshot.model_validate(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Falha lendo snapshot de %s: %s", path, exc)
        return None


def load() -> Optional[Snapshot]:
    """Carrega o snapshot do disco na memoria. Idempotente.

    Ordem de preferência:
      1) CACHE_FILE (DATA_DIR) — snapshot mais recente
      2) SEED_FILE (imagem)    — fallback embarcado se cache não acessível
    """
    global _snapshot
    with _lock:
        if _snapshot is not None:
            return _snapshot

        _ensure_cache_file()

        if CACHE_FILE.exists():
            snap = _load_file(CACHE_FILE)
            if snap is not None:
                _snapshot = snap
                logger.info("Cache carregado (%d livros, fetched_at=%s) de %s",
                            snap.count, snap.fetched_at, CACHE_FILE)
                return _snapshot

        if SEED_FILE.exists():
            snap = _load_file(SEED_FILE)
            if snap is not None:
                _snapshot = snap
                logger.warning(
                    "Servindo a partir do SEED em memória (%d livros). "
                    "Cache em disco indisponível — POST /admin/refresh quando o "
                    "volume estiver gravável.", snap.count,
                )
                return _snapshot

        logger.error("Nenhuma fonte de dados disponível (cache=%s, seed=%s)",
                     CACHE_FILE.exists(), SEED_FILE.exists())
        return None


def save(books: list[Book], source_url: str) -> Snapshot:
    """Persiste um snapshot atualizado no disco a atualiza uma copia em memoria."""
    global _snapshot
    snapshot = Snapshot(
        fetched_at=datetime.now(timezone.utc),
        source_url=source_url,
        count=len(books),
        books=books,
    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(snapshot.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
    tmp.replace(CACHE_FILE)
    with _lock:
        _snapshot = snapshot
    logger.info("Saved %d books to cache", len(books))
    return snapshot


def current() -> Optional[Snapshot]:
    """Retorna o snapshot em memoria, carregando do disco se precisar."""
    return _snapshot or load()
