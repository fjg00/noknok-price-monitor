"""Read-side queries that power the dashboard/API."""
from __future__ import annotations

from sqlalchemy import select

from .models import Match, PricePoint, Product, Store


def _latest_price(session, product_id: int):
    return session.scalar(
        select(PricePoint)
        .where(PricePoint.product_id == product_id)
        .order_by(PricePoint.observed_at.desc())
        .limit(1)
    )


def comparison_rows(session, base_key: str = "noknok") -> list[dict]:
    """One row per NokNok product with its matched competitor prices."""
    base_store = session.scalar(select(Store).where(Store.key == base_key))
    if base_store is None:
        return []

    rows: list[dict] = []
    base_products = session.scalars(
        select(Product).where(Product.store_id == base_store.id).order_by(Product.name)
    ).all()

    for bp in base_products:
        bp_price = _latest_price(session, bp.id)
        if bp_price is None:
            continue

        competitors = []
        matches = session.scalars(
            select(Match).where(Match.base_product_id == bp.id)
        ).all()
        for m in matches:
            cp = session.get(Product, m.competitor_product_id)
            cp_price = _latest_price(session, cp.id)
            if cp_price is None:
                continue
            store = session.get(Store, cp.store_id)
            diff = round(cp_price.price - bp_price.price, 2)
            pct = round(diff / bp_price.price * 100, 1) if bp_price.price else 0.0
            competitors.append({
                "store": store.name,
                "store_key": store.key,
                "name": cp.name,
                "price": cp_price.price,
                "in_stock": cp_price.in_stock,
                "diff": diff,
                "pct": pct,
                "score": round(m.score, 1),
                "cheaper_than_noknok": diff < 0,
                "url": cp.url,
            })

        comp_prices = [c["price"] for c in competitors if c["in_stock"]]
        rows.append({
            "product": bp.name,
            "brand": bp.brand,
            "size": bp.size,
            "category": bp.category,
            "noknok_price": bp_price.price,
            "currency": bp_price.currency,
            "competitors": competitors,
            "min_competitor": min(comp_prices) if comp_prices else None,
            "noknok_is_cheapest": (
                bp_price.price <= min(comp_prices) if comp_prices else None
            ),
        })
    return rows


def price_history(session, product_id: int, limit: int = 50) -> list[dict]:
    points = session.scalars(
        select(PricePoint)
        .where(PricePoint.product_id == product_id)
        .order_by(PricePoint.observed_at.desc())
        .limit(limit)
    ).all()
    return [
        {"price": p.price, "observed_at": p.observed_at.isoformat(), "in_stock": p.in_stock}
        for p in reversed(points)
    ]


def store_stats(session) -> list[dict]:
    stats = []
    for store in session.scalars(select(Store)).all():
        count = session.scalar(
            select(Product).where(Product.store_id == store.id).limit(1)
        )
        n = len(session.scalars(
            select(Product.id).where(Product.store_id == store.id)
        ).all())
        stats.append({"key": store.key, "name": store.name,
                      "is_base": store.is_base, "products": n})
    return stats
