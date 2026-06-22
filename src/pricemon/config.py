"""Configuration loading for the price-monitoring system."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Project root = three levels up from this file (src/pricemon/config.py).
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "competitors.yaml"
DB_PATH = ROOT / "data" / "pricemon.db"


@dataclass
class StoreConfig:
    key: str
    name: str
    mode: str = "demo"
    base_url: str = ""
    currency: str = "USD"
    enabled: bool = True
    selectors: dict = field(default_factory=dict)


@dataclass
class AppConfig:
    base_store: StoreConfig
    competitors: list[StoreConfig]
    categories: list[str]

    @property
    def all_stores(self) -> list[StoreConfig]:
        return [self.base_store, *self.competitors]

    def store(self, key: str) -> StoreConfig | None:
        return next((s for s in self.all_stores if s.key == key), None)


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """Read competitors.yaml into typed config objects."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    base = StoreConfig(**raw["base_store"])
    competitors = [
        StoreConfig(**c) for c in raw.get("competitors", []) if c.get("enabled", True)
    ]
    categories = raw.get("categories", [])
    return AppConfig(base_store=base, competitors=competitors, categories=categories)
