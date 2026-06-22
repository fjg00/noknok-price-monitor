"""Thread-safe scrape runner + live status, shared by the scheduler, the
startup bootstrap, and the manual /api/refresh endpoint.

Keeps a single in-memory snapshot of 'what is the scraper doing right now'
so the dashboard can show a live status bar without a database round-trip.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from .config import load_config
from .pipeline import scrape_all

# One global lock so two scrapes never overlap (scheduler + manual click).
_lock = threading.Lock()

_status: dict = {
    "state": "idle",            # idle | scraping
    "last_started": None,
    "last_finished": None,
    "last_duration_sec": None,
    "last_summary": None,       # per-store product counts
    "last_error": None,
    "interval_min": 30,
    "runs": 0,
}
_status_lock = threading.Lock()


def get_status() -> dict:
    with _status_lock:
        return dict(_status)


def set_interval(minutes: int) -> None:
    with _status_lock:
        _status["interval_min"] = minutes


def _update(**kw) -> None:
    with _status_lock:
        _status.update(kw)


def seed_status_from_db() -> None:
    """On boot, show the most recent stored scrape time immediately
    (status is in-memory and otherwise resets to 'never' each restart)."""
    from sqlalchemy import func, select

    from .db import get_session
    from .models import PricePoint

    session = get_session()
    try:
        latest = session.scalar(select(func.max(PricePoint.observed_at)))
    finally:
        session.close()
    if latest is not None:
        iso = latest.replace(tzinfo=timezone.utc).isoformat()
        _update(last_finished=iso)


def run_scrape(trigger: str = "manual") -> dict:
    """Run one scrape+match pass. Returns a small result dict.

    If a scrape is already running, returns immediately with busy=True.
    """
    if not _lock.acquire(blocking=False):
        return {"busy": True, "trigger": trigger}

    started = datetime.now(timezone.utc)
    _update(state="scraping", last_started=started.isoformat(), last_error=None)
    try:
        summary = scrape_all(load_config())
        finished = datetime.now(timezone.utc)
        with _status_lock:
            _status.update(
                state="idle",
                last_finished=finished.isoformat(),
                last_duration_sec=round((finished - started).total_seconds(), 1),
                last_summary=summary.get("stores"),
                runs=_status["runs"] + 1,
            )
        return {"busy": False, "trigger": trigger, "summary": summary.get("stores")}
    except Exception as exc:  # never crash the scheduler/web process
        _update(state="idle", last_error=str(exc),
                last_finished=datetime.now(timezone.utc).isoformat())
        return {"busy": False, "trigger": trigger, "error": str(exc)}
    finally:
        _lock.release()


def run_scrape_async(trigger: str = "startup") -> threading.Thread:
    """Fire a scrape in a background thread (non-blocking)."""
    t = threading.Thread(target=run_scrape, args=(trigger,), daemon=True)
    t.start()
    return t
