"""Orchestration: scrape every store, persist products + prices, then
rebuild fuzzy matches between NokNok and each competitor."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from .config import AppConfig, load_config
from .db import session_scope
from .matching import best_matches, normalize
from .models import Match, PricePoint, Product, Store
from .scrapers import ScrapedProduct, build_scraper


def _upsert_store(session, cfg, is_base: bool) -> Store:
    store = session.scalar(select(Store).where(Store.key == cfg.key))
    if store is None:
        store = Store(key=cfg.key, name=cfg.name, is_base=is_base)
        session.add(store)
        session.flush()
    else:
        store.name = cfg.name
        store.is_base = is_base
    return store


def _upsert_product(session, store: Store, sp: ScrapedProduct) -> Product:
    prod = session.scalar(
        select(Product).where(
            Product.store_id == store.id, Product.external_id == sp.external_id
        )
    )
    size = sp.extract_size()
    norm = normalize(sp.name, sp.brand, size)
    if prod is None:
        prod = Product(store_id=store.id, external_id=sp.external_id)
        session.add(prod)
    prod.name = sp.name
    prod.brand = sp.brand
    prod.size = size
    prod.category = sp.category
    prod.image_url = sp.image_url
    prod.url = sp.url
    prod.norm_key = norm
    session.flush()
    return prod


def scrape_all(config: AppConfig | None = None) -> dict:
    """Run every enabled scraper and persist a fresh price snapshot."""
    config = config or load_config()
    summary = {"stores": {}, "started_at": datetime.now(timezone.utc).isoformat()}

    with session_scope() as session:
        for cfg in config.all_stores:
            is_base = cfg.key == config.base_store.key
            store = _upsert_store(session, cfg, is_base)
            scraper = build_scraper(cfg)
            try:
                items = scraper.scrape(config.categories)
            except Exception as exc:  # one store failing must not kill the run
                summary["stores"][cfg.key] = {"error": str(exc)}
                continue

            for sp in items:
                prod = _upsert_product(session, store, sp)
                session.add(
                    PricePoint(
                        product_id=prod.id,
                        price=sp.price,
                        currency=sp.currency,
                        in_stock=sp.in_stock,
                    )
                )
            summary["stores"][cfg.key] = {"products": len(items)}

    rebuild_matches(config)
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    return summary


def rebuild_matches(config: AppConfig | None = None, threshold: float = 72.0) -> int:
    """Recompute fuzzy matches between NokNok and each competitor."""
    config = config or load_config()
    total = 0
    with session_scope() as session:
        base_store = session.scalar(
            select(Store).where(Store.key == config.base_store.key)
        )
        if base_store is None:
            return 0

        base_products = [
            {"id": p.id, "external_id": p.external_id, "norm_key": p.norm_key,
             "brand": p.brand, "size": p.size}
            for p in session.scalars(
                select(Product).where(Product.store_id == base_store.id)
            )
        ]
        base_by_ext = {bp["external_id"]: bp["id"] for bp in base_products}

        for cfg in config.competitors:
            store = session.scalar(select(Store).where(Store.key == cfg.key))
            if store is None:
                continue
            comp_products = [
                {"id": p.id, "external_id": p.external_id, "norm_key": p.norm_key,
                 "brand": p.brand, "size": p.size}
                for p in session.scalars(
                    select(Product).where(Product.store_id == store.id)
                )
            ]
            comp_by_ext = {cp["external_id"]: cp["id"] for cp in comp_products}

            candidates = best_matches(base_products, comp_products, threshold)
            for cand in candidates:
                bp_id = base_by_ext[cand.base_external_id]
                cp_id = comp_by_ext[cand.competitor_external_id]
                existing = session.scalar(
                    select(Match).where(
                        Match.base_product_id == bp_id,
                        Match.competitor_product_id == cp_id,
                    )
                )
                if existing is None:
                    session.add(
                        Match(
                            base_product_id=bp_id,
                            competitor_product_id=cp_id,
                            score=cand.score,
                        )
                    )
                    total += 1
                else:
                    existing.score = cand.score
    return total
