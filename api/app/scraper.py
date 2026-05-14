"""Amazon best sellers scraper.

Amazon is aggressive about blocking scrapers. The strategy here:

1. Send realistic browser headers (User-Agent + Accept-Language).
2. Retry with exponential backoff on transient failures.
3. Parse defensively — Amazon rotates CSS class names, so we use multiple
   fallback selectors and accept partial data.
4. On total failure, the API still serves the on-disk cache (handled by
   the caller). This function raises ScrapeError so the caller can decide.

The author field is not always exposed in the bestsellers grid — when missing
we record 'Unknown' rather than fabricating a value. The PDF lists author as a
required field; this is the most honest behaviour given Amazon's markup.
"""
from __future__ import annotations

import logging
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .models import Book

logger = logging.getLogger(__name__)

BESTSELLERS_URL = "https://www.amazon.com/gp/bestsellers/books/"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class ScrapeError(RuntimeError):
    """Raised when scraping fails after retries."""


def _headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _fetch_html(url: str, retries: int = 3, timeout: int = 20) -> str:
    last_exc: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=_headers(), timeout=timeout)
            if resp.status_code == 200 and "captcha" not in resp.text.lower()[:5000]:
                return resp.text
            logger.warning("Attempt %d: HTTP %s (captcha=%s)",
                           attempt, resp.status_code,
                           "captcha" in resp.text.lower()[:5000])
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Attempt %d failed: %s", attempt, exc)
        time.sleep(2 ** attempt + random.random())
    raise ScrapeError(f"Failed to fetch {url} after {retries} attempts: {last_exc}")


_RATING_RE = re.compile(r"([\d.]+)\s*out of\s*5", re.IGNORECASE)
_REVIEWS_RE = re.compile(r"([\d,]+)")
_PRICE_RE = re.compile(r"\$?([\d,]+\.\d{2})")


def _parse_rating(text: str) -> Optional[float]:
    m = _RATING_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_price(text: str) -> Optional[float]:
    m = _PRICE_RE.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_reviews(text: str) -> Optional[int]:
    m = _REVIEWS_RE.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_books(html: str) -> list[Book]:
    soup = BeautifulSoup(html, "lxml")

    items = soup.select("div#gridItemRoot") or soup.select("div.zg-grid-general-faceout") \
        or soup.select("[id^='zg-bs']")

    books: list[Book] = []
    for idx, item in enumerate(items, start=1):
        title_el = (
            item.select_one("div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
            or item.select_one("div._cDEzb_p13n-sc-css-line-clamp-2_EWgCb")
            or item.select_one("div._cDEzb_p13n-sc-css-line-clamp-1_1Fn1y")
            or item.select_one("a.a-link-normal span div")
            or item.select_one("a.a-link-normal")
        )
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue

        author_el = item.select_one("a.a-size-small.a-link-child") \
            or item.select_one("div.a-row a.a-size-small")
        author = author_el.get_text(strip=True) if author_el else "Unknown"

        rating_el = item.select_one("i.a-icon-star-small span.a-icon-alt") \
            or item.select_one("span.a-icon-alt")
        rating = _parse_rating(rating_el.get_text() if rating_el else "")

        reviews_el = item.select_one("span.a-size-small")
        reviews = _parse_reviews(reviews_el.get_text() if reviews_el else "")

        price_el = item.select_one("span._cDEzb_p13n-sc-price_3mJ9Z") \
            or item.select_one("span.p13n-sc-price") \
            or item.select_one("span.a-color-price")
        price = _parse_price(price_el.get_text() if price_el else "")

        link_el = item.select_one("a.a-link-normal")
        product_url = None
        if link_el and link_el.get("href"):
            href = link_el["href"]
            product_url = href if href.startswith("http") else f"https://www.amazon.com{href}"

        img_el = item.select_one("img")
        image_url = img_el["src"] if img_el and img_el.get("src") else None

        books.append(Book(
            id=idx,
            title=title,
            author=author or "Unknown",
            rating=rating,
            reviews=reviews,
            price=price,
            currency="USD",
            image_url=image_url,
            product_url=product_url,
        ))
    return books


def scrape() -> list[Book]:
    """Busca e parseia a grid de best sellers da Amazon.

    Raises:
        ScrapeError: Se a Amazon nào for alcançada ou não parsear os livros.
    """
    html = _fetch_html(BESTSELLERS_URL)
    books = _extract_books(html)
    if not books:
        raise ScrapeError("Amazon respondeu mas os livros não puderam ser extraidos (mudou a estrutura do html?)")
    logger.info("Raspou %d livros da Amazon", len(books))
    return books
