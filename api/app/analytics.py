from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Iterable

from .models import AuthorCount, Book, Overview, PriceBucket, Snapshot


def overview(snapshot: Snapshot) -> Overview:
    books = snapshot.books
    ratings = [b.rating for b in books if b.rating is not None]
    prices = [b.price for b in books if b.price is not None]
    return Overview(
        total_books=len(books),
        avg_rating=round(mean(ratings), 2) if ratings else None,
        avg_price=round(mean(prices), 2) if prices else None,
        min_price=min(prices) if prices else None,
        max_price=max(prices) if prices else None,
        unique_authors=len({b.author for b in books if b.author}),
        fetched_at=snapshot.fetched_at,
    )


def top_rated(books: Iterable[Book], limit: int = 10) -> list[Book]:
    rated = [b for b in books if b.rating is not None]
    return sorted(
        rated,
        key=lambda b: (b.rating or 0, b.reviews or 0),
        reverse=True,
    )[:limit]


def by_author(books: Iterable[Book]) -> list[AuthorCount]:
    buckets: dict[str, list[Book]] = defaultdict(list)
    for b in books:
        buckets[b.author].append(b)
    out: list[AuthorCount] = []
    for author, items in buckets.items():
        ratings = [b.rating for b in items if b.rating is not None]
        out.append(AuthorCount(
            author=author,
            books=len(items),
            avg_rating=round(mean(ratings), 2) if ratings else None,
        ))
    return sorted(out, key=lambda a: (a.books, a.avg_rating or 0), reverse=True)


_PRICE_BUCKETS: list[tuple[str, float, float]] = [
    ("0-10", 0.0, 10.0),
    ("10-15", 10.0, 15.0),
    ("15-20", 15.0, 20.0),
    ("20-30", 20.0, 30.0),
    ("30+", 30.0, float("inf")),
]


def price_ranges(books: Iterable[Book]) -> list[PriceBucket]:
    counts = {label: 0 for label, _, _ in _PRICE_BUCKETS}
    for b in books:
        if b.price is None:
            continue
        for label, lo, hi in _PRICE_BUCKETS:
            if lo <= b.price < hi:
                counts[label] += 1
                break
    return [
        PriceBucket(bucket=label, min_price=lo, max_price=hi if hi != float("inf") else 999.0, books=counts[label])
        for label, lo, hi in _PRICE_BUCKETS
    ]
