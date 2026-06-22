"""Background scheduler that re-scrapes prices on an interval — the
'live' part of the system. Delegates the actual work to runner.run_scrape
so the scheduler, startup bootstrap, and manual refresh all share one
lock and one status snapshot."""
from __future__ import annotations

import os

from apscheduler.schedulers.background import BackgroundScheduler

from .runner import run_scrape, set_interval

# Refresh interval in minutes (override with PRICEMON_INTERVAL_MIN env var).
INTERVAL_MIN = int(os.getenv("PRICEMON_INTERVAL_MIN", "30"))

_scheduler: BackgroundScheduler | None = None


def _job():
    result = run_scrape(trigger="schedule")
    if result.get("busy"):
        print("[scheduler] skipped: a scrape is already running")
    elif result.get("error"):
        print(f"[scheduler] scrape failed: {result['error']}")
    else:
        print(f"[scheduler] scrape complete: {result.get('summary')}")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    set_interval(INTERVAL_MIN)
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _job, "interval", minutes=INTERVAL_MIN, id="scrape", max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    print(f"[scheduler] started; scraping every {INTERVAL_MIN} min")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
