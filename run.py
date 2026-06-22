#!/usr/bin/env python
"""Entry point for the NokNok price-monitoring system.

Usage:
  python run.py scrape     # run one scrape + match pass, then exit
  python run.py serve      # start the dashboard (with background scheduler)
  python run.py match      # rebuild fuzzy matches from existing data
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pricemon.config import load_config  # noqa: E402
from pricemon.db import init_engine  # noqa: E402


def cmd_scrape():
    from pricemon.pipeline import scrape_all
    init_engine()
    summary = scrape_all(load_config())
    print("Scrape summary:")
    for store, info in summary["stores"].items():
        print(f"  {store:12s} {info}")


def cmd_match():
    from pricemon.pipeline import rebuild_matches
    init_engine()
    n = rebuild_matches(load_config())
    print(f"Created/updated {n} matches.")


def cmd_test():
    """Test one store's scraper live and print a sample (no DB writes).

    Usage: python run.py test <store_key>   e.g. python run.py test carrefour
    """
    from pricemon.scrapers import build_scraper
    cfg = load_config()
    key = sys.argv[2] if len(sys.argv) > 2 else ""
    store = cfg.store(key)
    if store is None:
        print(f"Unknown store '{key}'. Options: {[s.key for s in cfg.all_stores]}")
        return
    print(f"Testing scraper for {store.name} (mode={store.mode})...")
    try:
        items = build_scraper(store).scrape(cfg.categories)
    except Exception as exc:
        print(f"\n  FAILED: {exc}")
        return
    print(f"\n  Got {len(items)} products. Sample:")
    for it in items[:10]:
        print(f"    {it.currency} {it.price:>8.2f}  {it.name[:50]}")


def cmd_serve():
    import os
    import uvicorn
    # Cloud hosts (Render/Railway) inject $PORT and need host 0.0.0.0.
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Dashboard -> http://{('127.0.0.1' if host=='0.0.0.0' else host)}:{port}")
    uvicorn.run("pricemon.api:app", host=host, port=port, reload=False)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    {"scrape": cmd_scrape, "match": cmd_match, "serve": cmd_serve,
     "test": cmd_test}.get(cmd, lambda: print(__doc__))()


if __name__ == "__main__":
    main()
