"""Base scraper interface and the shared ScrapedProduct record."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import StoreConfig

# Matches sizes like "500g", "1.5 L", "6x330ml", "250 ml".
_SIZE_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*(?:x\s*\d+(?:\.\d+)?)?\s*(?:kg|g|gr|l|ml|cl|pcs|pack|x))",
    re.IGNORECASE,
)


@dataclass
class ScrapedProduct:
    """Normalized product record returned by every scraper."""

    external_id: str
    name: str
    price: float
    currency: str = "USD"
    brand: str | None = None
    size: str | None = None
    category: str | None = None
    image_url: str | None = None
    url: str | None = None
    in_stock: bool = True

    def extract_size(self) -> str | None:
        if self.size:
            return self.size
        m = _SIZE_RE.search(self.name or "")
        return m.group(1).replace(" ", "").lower() if m else None


class BaseScraper:
    """Subclass and implement `scrape()` to return ScrapedProduct records."""

    def __init__(self, cfg: StoreConfig):
        self.cfg = cfg

    @property
    def key(self) -> str:
        return self.cfg.key

    def scrape(self, categories: list[str]) -> list[ScrapedProduct]:
        raise NotImplementedError
