"""CSV-backed 'scraper' for stores with no scrapable web catalog.

NokNok is app-only — noknok.co is a marketing site and the catalog lives
behind the mobile app's Ocelot API gateway (api.noknok.co), which isn't
publicly browsable. So NokNok's own prices are sourced from a maintained
CSV instead of HTTP scraping.

CSV columns (header required):
    external_id,name,brand,size,category,price,currency,in_stock,url

Keep this file updated from the app (or, later, point it at a captured
app-API export). Path is taken from `selectors.csv_path` in the config,
relative to the project root.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..config import ROOT
from .base import BaseScraper, ScrapedProduct


class ManualCsvScraper(BaseScraper):
    def scrape(self, categories: list[str]) -> list[ScrapedProduct]:
        rel = self.cfg.selectors.get("csv_path", f"data/{self.key}_prices.csv")
        path = (ROOT / rel).resolve()
        if not path.exists():
            print(f"[{self.key}] price CSV not found at {path} — skipping. "
                  f"Create it to feed {self.cfg.name} prices.")
            return []

        out: list[ScrapedProduct] = []
        with path.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for i, row in enumerate(reader):
                price_raw = (row.get("price") or "").strip()
                if not price_raw:
                    continue
                try:
                    price = float(price_raw.replace(",", "."))
                except ValueError:
                    continue
                ext = (row.get("external_id") or "").strip() or f"{self.key}-{i:04d}"
                in_stock = (row.get("in_stock") or "1").strip().lower() not in (
                    "0", "false", "no", "out",
                )
                out.append(
                    ScrapedProduct(
                        external_id=ext,
                        name=(row.get("name") or "").strip(),
                        price=price,
                        currency=(row.get("currency") or self.cfg.currency).strip(),
                        brand=(row.get("brand") or "").strip() or None,
                        size=(row.get("size") or "").strip() or None,
                        category=(row.get("category") or "").strip() or None,
                        url=(row.get("url") or "").strip() or None,
                        in_stock=in_stock,
                    )
                )
        return out
