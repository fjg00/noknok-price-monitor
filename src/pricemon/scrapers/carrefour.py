"""Carrefour Lebanon scraper.

Carrefour Lebanon (MAF) sits behind Akamai Bot Manager — direct requests,
headless browsers, and even real Chrome all get HTTP 403 "Access Denied".
The only reliable way through is a web-unblocking service (see _unblocker.py),
which fetches the fully JS-rendered category page; we then parse the product
grid from the HTML.

MAF storefronts tag products with stable `data-testid` attributes, so the
default selectors below usually work. If Carrefour changes them, just edit
`selectors` in competitors.yaml — no code change needed.

Setup:
  1. Get a key from ZenRows or ScraperAPI (free trial).
  2. setx SCRAPER_API_KEY "your-key"   (PowerShell: $env:SCRAPER_API_KEY="...")
  3. In competitors.yaml set carrefour `enabled: true` and list real category
     URLs under selectors.category_urls (copy them from the site's menu).
  4. python run.py test carrefour
"""
from __future__ import annotations

import re

from .base import BaseScraper, ScrapedProduct
from . import _unblocker

_PRICE_RE = re.compile(r"\d[\d,]*\.?\d*")


def _num(text: str | None) -> float | None:
    if not text:
        return None
    m = _PRICE_RE.search(text.replace(",", ""))
    return float(m.group()) if m else None


class CarrefourScraper(BaseScraper):
    # Sensible MAF defaults; override in competitors.yaml -> selectors.
    DEFAULTS = {
        "product_card": "[data-testid='product_card'], li[class*='product']",
        "name": "[data-testid='product_name'], a[data-testid='product_name']",
        "price": "[data-testid='product_price'], [class*='price']",
        "link": "a",
        "image": "img",
    }

    def scrape(self, categories: list[str]) -> list[ScrapedProduct]:
        from selectolax.parser import HTMLParser

        if not _unblocker.is_configured():
            raise _unblocker.UnblockerNotConfigured(
                "Carrefour is enabled but SCRAPER_API_KEY is not set. "
                "Add a ZenRows/ScraperAPI key to scrape past Akamai."
            )

        sel = {**self.DEFAULTS, **self.cfg.selectors}
        urls = self.cfg.selectors.get("category_urls") or []
        if not urls:
            raise RuntimeError(
                "Carrefour has no category_urls configured. Copy real category "
                "page URLs from carrefourlebanon.com into selectors.category_urls."
            )

        out: list[ScrapedProduct] = []
        seen: set[str] = set()
        for url in urls:
            html = _unblocker.fetch(url, render=True, country="lb")
            if "Access Denied" in html[:500]:
                print(f"[carrefour] still blocked for {url} — check unblocker plan "
                      f"(needs JS render + premium/residential proxies).")
                continue
            tree = HTMLParser(html)
            cat = self._category_from_url(url)
            for card in tree.css(sel["product_card"]):
                item = self._parse(card, sel, cat, url)
                if item and item.external_id not in seen:
                    seen.add(item.external_id)
                    out.append(item)
        return out

    def _category_from_url(self, url: str) -> str:
        return url.rstrip("/").split("/")[-1].split("?")[0]

    def _parse(self, card, sel, category, page_url) -> ScrapedProduct | None:
        name_el = card.css_first(sel["name"])
        price_el = card.css_first(sel["price"])
        if not name_el or not price_el:
            return None
        name = name_el.text(strip=True)
        price = _num(price_el.text(strip=True))
        if not name or price is None:
            return None
        link_el = card.css_first(sel["link"])
        href = link_el.attributes.get("href") if link_el else None
        if href and href.startswith("/"):
            href = "https://www.carrefourlebanon.com" + href
        img_el = card.css_first(sel["image"])
        image = (img_el.attributes.get("src") or img_el.attributes.get("data-src")) if img_el else None
        slug = (href or name).rstrip("/").split("/")[-1][:80]
        return ScrapedProduct(
            external_id=f"{self.key}-{slug}"[:128],
            name=name,
            price=price,
            currency=self.cfg.currency,
            category=category,
            image_url=image,
            url=href,
        )
