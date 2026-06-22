"""Real scraper for Magento storefronts (server-rendered product grids).

Verified against Spinneys Lebanon (https://www.spinneyslebanon.com), which
renders product listing pages server-side with prices in a
`data-price-amount` attribute. Walks each configured category, paginating
with `?p=N`, until a page yields no products or the page cap is hit.

Config (competitors.yaml):
  mode: magento
  base_url: "https://www.spinneyslebanon.com"
  categories: [beverages, snacks-candy, ...]      # -> /{cat}.html
  max_pages: 5                                     # optional, per category
"""
from __future__ import annotations

import time

from .base import BaseScraper, ScrapedProduct

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


class MagentoScraper(BaseScraper):
    REQUEST_DELAY = 1.2  # polite delay between page requests
    DEFAULT_MAX_PAGES = 5

    def scrape(self, categories: list[str]) -> list[ScrapedProduct]:
        import httpx
        from selectolax.parser import HTMLParser

        cats = self.cfg.selectors.get("categories") or categories
        max_pages = int(self.cfg.selectors.get("max_pages", self.DEFAULT_MAX_PAGES))
        base = self.cfg.base_url.rstrip("/")

        out: list[ScrapedProduct] = []
        seen: set[str] = set()
        headers = {"User-Agent": UA, "Accept-Language": "en,ar;q=0.8"}

        with httpx.Client(headers=headers, timeout=25.0, follow_redirects=True) as client:
            for cat in cats:
                for page in range(1, max_pages + 1):
                    url = f"{base}/{cat}.html"
                    if page > 1:
                        url += f"?p={page}"
                    try:
                        resp = client.get(url)
                        if resp.status_code == 404:
                            break
                        resp.raise_for_status()
                    except httpx.HTTPError as exc:
                        print(f"[{self.key}] fetch failed {url}: {exc}")
                        break

                    tree = HTMLParser(resp.text)
                    cards = tree.css("li.product-item")
                    if not cards:
                        break

                    new_on_page = 0
                    for card in cards:
                        item = self._parse_card(card, cat)
                        if item and item.external_id not in seen:
                            seen.add(item.external_id)
                            out.append(item)
                            new_on_page += 1

                    # No genuinely new products -> we've paged past the end.
                    if new_on_page == 0:
                        break
                    time.sleep(self.REQUEST_DELAY)
        return out

    def _parse_card(self, card, category: str) -> ScrapedProduct | None:
        name_el = card.css_first(".product-item-name a, a.product-item-link")
        price_el = card.css_first("[data-price-amount]")
        if not name_el or not price_el:
            return None

        name = name_el.text(strip=True)
        raw_amount = price_el.attributes.get("data-price-amount")
        try:
            price = float(raw_amount)
        except (TypeError, ValueError):
            return None

        link = name_el.attributes.get("href")
        img = card.css_first("img.product-image-photo, img")
        image = img.attributes.get("src") or img.attributes.get("data-src") if img else None

        # Magento product URLs are stable -> derive a stable external id from the slug.
        slug = (link or name).rstrip("/").split("/")[-1].replace(".html", "")
        in_stock = "out of stock" not in card.text().lower()

        return ScrapedProduct(
            external_id=f"{self.key}-{slug}"[:128],
            name=name,
            price=price,
            currency=self.cfg.currency,
            category=category,
            image_url=image,
            url=link,
            in_stock=in_stock,
        )
