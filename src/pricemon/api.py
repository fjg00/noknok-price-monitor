"""FastAPI app: self-running live dashboard + JSON API for the price monitor.

Designed to run as an always-on website:
  - on startup it initializes the DB, starts the 30-min scheduler, and (if
    there's no data yet) kicks off an immediate background scrape so the
    site has fresh prices the moment it comes online;
  - the dashboard polls /api/comparison + /api/status and updates live.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from .config import load_config
from .db import get_session, init_engine
from .models import PricePoint
from .queries import comparison_rows, store_stats
from .runner import get_status, run_scrape_async, seed_status_from_db

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# Jinja2's LRUCache is incompatible with Python 3.14; disable template caching.
templates.env.cache = None


def _has_data() -> bool:
    session = get_session()
    try:
        return session.scalar(select(PricePoint.id).limit(1)) is not None
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    seed_status_from_db()
    if os.getenv("PRICEMON_NO_SCHEDULER") != "1":
        from .scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        # Self-bootstrap: if the DB is empty (e.g. fresh deploy), scrape now
        # in the background so the site isn't blank until the first timer tick.
        if not _has_data():
            run_scrape_async(trigger="startup")
        yield
        stop_scheduler()
    else:
        yield


app = FastAPI(title="NokNok Price Monitor", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    session = get_session()
    try:
        rows = comparison_rows(session)
        stats = store_stats(session)
    finally:
        session.close()
    cfg = load_config()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "rows": rows,
            "stats": stats,
            "competitors": [c.name for c in cfg.competitors],
        },
    )


@app.get("/api/comparison")
def api_comparison():
    session = get_session()
    try:
        return JSONResponse(comparison_rows(session))
    finally:
        session.close()


@app.get("/api/stats")
def api_stats():
    session = get_session()
    try:
        return JSONResponse(store_stats(session))
    finally:
        session.close()


@app.get("/api/status")
def api_status():
    """Live scraper status for the dashboard status bar."""
    return JSONResponse(get_status())


@app.post("/api/refresh")
def api_refresh():
    """Trigger an immediate scrape in the background (non-blocking)."""
    run_scrape_async(trigger="manual")
    return JSONResponse({"started": True, **get_status()})


@app.get("/healthz")
def healthz():
    return {"ok": True}
