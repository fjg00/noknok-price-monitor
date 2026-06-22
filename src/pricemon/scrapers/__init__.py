"""Scraper adapters. One mode per data source, all sharing BaseScraper."""
from __future__ import annotations

from ..config import StoreConfig
from .base import BaseScraper, ScrapedProduct
from .generic_http import GenericHttpScraper
from .magento import MagentoScraper
from .manual_csv import ManualCsvScraper

# Map a config `mode` -> scraper class.
MODES: dict[str, type[BaseScraper]] = {
    "magento": MagentoScraper,     # server-rendered Magento (Spinneys ✓)
    "manual_csv": ManualCsvScraper,  # CSV-fed store (NokNok app-only base)
    "http": GenericHttpScraper,    # generic config-driven HTML scrape
}

# Per-store overrides for sites that need bespoke logic (e.g. JSON API,
# Playwright). Register here as you implement them.
SPECIALIZED: dict[str, type[BaseScraper]] = {
    # "carrefour": CarrefourApiScraper,
    # "aoun": LeCharcutierBrowserScraper,
}


def build_scraper(cfg: StoreConfig) -> BaseScraper:
    """Factory: pick the right scraper for a store based on config."""
    if cfg.key in SPECIALIZED:
        return SPECIALIZED[cfg.key](cfg)
    scraper_cls = MODES.get(cfg.mode)
    if scraper_cls is None:
        raise ValueError(
            f"Unknown scraper mode '{cfg.mode}' for store '{cfg.key}'. "
            f"Valid modes: {', '.join(MODES)}"
        )
    return scraper_cls(cfg)


__all__ = ["BaseScraper", "ScrapedProduct", "build_scraper"]
