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

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))
CACHE_FILE = DATA_DIR / "cache.json"
SEED_FILE = DATA_DIR / "seed.json"

_lock = threading.Lock()
_snapshot: Optional[Snapshot] = None


def _ensure_cache_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists() and SEED_FILE.exists():
        shutil.copy(SEED_FILE, CACHE_FILE)
        logger.info("Cache populado em %s", SEED_FILE)


def load() -> Optional[Snapshot]:
    """Carrega o snapshot do disco na memoria. Idepotente."""
    global _snapshot
    with _lock:
        if _snapshot is not None:
            return _snapshot
        _ensure_cache_file()
        if not CACHE_FILE.exists():
            return None
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            _snapshot = Snapshot.model_validate(payload)
            logger.info("Loaded %d books from cache (fetched_at=%s)",
                        _snapshot.count, _snapshot.fetched_at)
            return _snapshot
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load cache: %s", exc)
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
