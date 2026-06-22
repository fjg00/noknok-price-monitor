"""Config-driven HTML scraper for real competitor sites.

Reads CSS selectors from competitors.yaml and walks each category page.
This is a TEMPLATE: most Lebanese grocery sites are JS-rendered or
bot-protected, so you'll typically need to (a) find the site's JSON API
in the network tab and call that here, or (b) switch the store to
mode: browser and use Playwright. The selector logic below works for
classic server-rendered product grids.

Politeness: identifies itself, rate-limits, and respects timeouts.
Always check a site's robots.txt / Terms of Service before enabling.
"""
from __future__ import annotations

import re
import time

from .base import BaseScraper, ScrapedProduct

_PRICE_RE = re.compile(r"[\d]+(?:[.,]\d{2})?")
UA = "NokNokPriceMonitor/0.1 (+https://www.noknok.com; price-research)"


def _parse_price(text: str | None) -> float | None:
    if not text:
        return None
    m = _PRICE_RE.search(text.replace(",", "."))
    return float(m.group()) if m else None


class GenericHttpScraper(BaseScraper):
    REQUEST_DELAY = 1.0  # seconds between page requests

    def _text(self, node, css: str) -> str | None:
        if not css:
            return None
        el = node.css_first(css)
        return el.text(strip=True) if el else None

    def _attr(self, node, css: str, attr: str) -> str | None:
        el = node.css_first(css) if css else node
        return el.attributes.get(attr) if el else None

    def scrape(self, categories: list[str]) -> list[ScrapedProduct]:
        # Imported lazily so demo mode runs without scraping deps installed.
        import httpx
        from selectolax.parser import HTMLParser

        sel = self.cfg.selectors
        if not sel.get("product_card"):
            raise RuntimeError(
                f"Store '{self.key}' is http mode but has no selectors configured. "
                "Fill in `selectors` in competitors.yaml or use mode: demo."
            )

        out: list[ScrapedProduct] = []
        headers = {"User-Agent": UA, "Accept-Language": "en,ar;q=0.8"}
        with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
            for cat in categories or [""]:
                url = f"{self.cfg.base_url}/category/{cat}".rstrip("/")
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:  # log + continue, don't kill the run
                    print(f"[{self.key}] fetch failed for {url}: {exc}")
                    continue

                tree = HTMLParser(resp.text)
                cards = tree.css(sel["product_card"])
                for i, card in enumerate(cards):
                    name = self._text(card, sel.get("name", ""))
                    price = _parse_price(self._text(card, sel.get("price", "")))
                    if not name or price is None:
                        continue
                    out.append(
                        ScrapedProduct(
                            external_id=f"{self.key}-{cat}-{i:03d}",
                            name=name,
                            price=price,
                            currency=self.cfg.currency,
                            brand=self._text(card, sel.get("brand", "")),
                            category=cat or None,
                            image_url=self._attr(card, sel.get("image", ""), "src"),
                            url=self._attr(card, "a", "href"),
                        )
                    )
                time.sleep(self.REQUEST_DELAY)
        return out
