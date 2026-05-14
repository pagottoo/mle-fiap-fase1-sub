from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Book(BaseModel):
    id: int = Field(..., description="Rank position in the Amazon best sellers list (1 = top)")
    title: str = Field(..., description="Book title")
    author: str = Field(..., description="Author name (or 'Unknown' when not exposed in the listing)")
    rating: Optional[float] = Field(
        None, ge=0, le=5, description="Average customer rating out of 5"
    )
    reviews: Optional[int] = Field(None, ge=0, description="Number of customer reviews")
    price: Optional[float] = Field(None, ge=0, description="Listed price in USD")
    currency: str = Field("USD", description="Currency of the listed price")
    image_url: Optional[str] = Field(None, description="Cover image URL")
    product_url: Optional[str] = Field(None, description="Amazon product page URL")


class Snapshot(BaseModel):
    fetched_at: datetime
    source_url: str
    count: int
    books: list[Book]


class HealthResponse(BaseModel):
    status: str
    fetched_at: Optional[datetime]
    books_in_cache: int


class RefreshResponse(BaseModel):
    status: str
    fetched_at: datetime
    books_fetched: int
    source: str = Field(..., description="'live' if Amazon responded, 'cache' if fallback used")


class Overview(BaseModel):
    total_books: int
    avg_rating: Optional[float]
    avg_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    unique_authors: int
    fetched_at: Optional[datetime]


class AuthorCount(BaseModel):
    author: str
    books: int
    avg_rating: Optional[float]


class PriceBucket(BaseModel):
    bucket: str
    min_price: float
    max_price: float
    books: int
