"""Web-unblocking client for bot-protected sites (e.g. Carrefour/Akamai).

Routes a request through a paid unblocking API that solves the anti-bot
challenge with residential proxies + JS rendering. Configure with ONE of:

    SCRAPER_PROVIDER=zenrows   SCRAPER_API_KEY=<your key>
    SCRAPER_PROVIDER=scraperapi SCRAPER_API_KEY=<your key>

If no key is set, `fetch()` raises a clear error telling you what to add.
Both providers offer free trials; set the env var and the Carrefour scraper
starts working with no code changes.
"""
from __future__ import annotations

import os

ZENROWS_ENDPOINT = "https://api.zenrows.com/v1/"
SCRAPERAPI_ENDPOINT = "https://api.scraperapi.com/"


class UnblockerNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(os.getenv("SCRAPER_API_KEY"))


def fetch(url: str, *, render: bool = True, country: str = "lb", timeout: float = 90.0) -> str:
    """Fetch `url` through the configured unblocker and return HTML/JSON text.

    render=True asks the provider to run JS (needed for React/Akamai pages).
    """
    import httpx

    key = os.getenv("SCRAPER_API_KEY")
    provider = os.getenv("SCRAPER_PROVIDER", "zenrows").lower()
    if not key:
        raise UnblockerNotConfigured(
            "Carrefour needs a web-unblocking service to get past Akamai. "
            "Set SCRAPER_API_KEY (and optionally SCRAPER_PROVIDER=zenrows|scraperapi). "
            "Free trials: https://www.zenrows.com  /  https://www.scraperapi.com"
        )

    if provider == "scraperapi":
        params = {
            "api_key": key,
            "url": url,
            "render": "true" if render else "false",
            "country_code": country,
        }
        endpoint = SCRAPERAPI_ENDPOINT
    else:  # zenrows (default)
        params = {
            "apikey": key,
            "url": url,
            "js_render": "true" if render else "false",
            "premium_proxy": "true",
            "proxy_country": country,
        }
        endpoint = ZENROWS_ENDPOINT

    with httpx.Client(timeout=timeout) as client:
        resp = client.get(endpoint, params=params)
        resp.raise_for_status()
        return resp.text
