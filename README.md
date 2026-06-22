# NokNok Price Monitor

Monitors competitor grocery prices via **real web scraping**, fuzzy-matches them
to NokNok products, stores price history, and surfaces it on a live,
auto-refreshing dashboard.

Repo: https://github.com/fjg00/noknok-price-monitor

### Deploy your live website (one click)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/fjg00/noknok-price-monitor)

Click the button → log in to Render with GitHub → **Apply**. You get a public URL
that scrapes on its own every 30 min. Full walkthrough in [DEPLOY.md](DEPLOY.md).

## Real-source status (investigated June 2026)

| Store | Domain | Source | Status |
|---|---|---|---|
| **NokNok** (base) | noknok.co | `manual_csv` | ⚠️ App-only — no web catalog (see below) |
| **Spinneys** | spinneyslebanon.com | `magento` | ✅ **Live scraping, ~1,400 products** |
| **Carrefour** | carrefourlebanon.com | `carrefour` | 🔑 Akamai-blocked — works with a web-unblocker key |
| **Aoun** (Le Charcutier) | lecharcutier.com | `aoun` | 🔑 Prices login-gated — works with an account |
| Toters | totersapp.com | — | ❌ App-only, no public web catalog |

### Enabling Carrefour & Aoun

Both are built and enabled; each just needs one credential (see [`.env.example`](.env.example)):

- **Carrefour** — protected by Akamai Bot Manager (every automated client gets
  403). Set `SCRAPER_API_KEY` (ZenRows/ScraperAPI, free trial); the scraper fetches
  the JS-rendered category pages through it and parses the product grid. Then put
  real category URLs in `carrefour.selectors.category_urls`. Test:
  `python run.py test carrefour`.
- **Aoun** — renders fine in a browser but only shows prices to logged-in users.
  Set `AOUN_USERNAME` / `AOUN_PASSWORD` (a real lecharcutier.com account); the
  scraper logs in with headless Chromium, reads LBP prices, and converts to USD via
  `aoun.selectors.lbp_per_usd`. Needs Playwright (`pip install playwright &&
  python -m playwright install chromium`). Test: `python run.py test aoun`.

Until you add the credential, each is skipped with a clear message — the rest of
the system keeps running.

**Why NokNok uses a CSV:** `noknok.co` is a marketing site; the real catalog lives
behind the mobile app's API gateway (`api.noknok.co`, an Ocelot gateway not publicly
browsable). So NokNok's own prices are maintained in `data/noknok_prices.csv` — edit
that file (or later wire it to a captured app-API export) to keep base prices current.
Everything is compared *against* these prices.

## How it works

```
 scrapers/ ──> pipeline ──> SQLite (products + price history)
   (one per       │              │
    competitor)   │              ├─> fuzzy matching (rapidfuzz)
                  │              │
 scheduler ───────┘              └─> FastAPI dashboard + JSON API
 (re-scrape every N min)
```

- **Scrapers** — `src/pricemon/scrapers/`. Each store maps to a `mode`:
  `MagentoScraper` (real, server-rendered Magento — Spinneys), `ManualCsvScraper`
  (CSV-fed, for app-only stores like NokNok), `GenericHttpScraper` (config-driven
  CSS selectors). Add a bespoke one (JSON API / Playwright) in `SPECIALIZED`.
- **Matching** — `matching.py` normalizes names (brand + name + size) and scores
  pairs with `rapidfuzz` token-set ratio plus brand/size bonuses.
- **Storage** — SQLite via SQLAlchemy; every scrape appends a `PricePoint`, so you
  keep full price history.
- **Live / self-running** — on startup it scrapes immediately (so the page is never
  blank), then APScheduler re-scrapes every `PRICEMON_INTERVAL_MIN` (default 30) on
  its own. The dashboard polls `/api/status` + `/api/comparison` and updates live —
  status dot, "last updated", a countdown to the next scrape, and a "Scrape now"
  button — no manual page reloads.

## Host it as a real website

See **[DEPLOY.md](DEPLOY.md)** — one-click free deploy to Render gives you a public
URL that runs 24/7 and scrapes by itself. The repo includes `render.yaml` and a
`Procfile`, and `run.py serve` already honors the host's `$PORT`/`$HOST`.

## Quick start (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python run.py scrape      # real scrape: Spinneys live + NokNok CSV, then match
python run.py serve       # open http://127.0.0.1:8000
```

The first `scrape` pulls ~1,400 live Spinneys products (8 categories, polite
1.2s/page delay) and matches them against `data/noknok_prices.csv`.

## Going live on a real site

1. Open `config/competitors.yaml`, set the store's `mode` to `http` (server-rendered)
   or `browser` (JS/SPA), and fill in real `base_url`, `categories`, and CSS
   `selectors`.
2. For JS-heavy / bot-protected sites (most LB grocery apps), the most reliable path
   is to find the site's JSON product API in the browser network tab and call it
   directly — add a specialized scraper in `scrapers/` and register it in
   `SPECIALIZED` in `scrapers/__init__.py`.
3. **Check each site's robots.txt and Terms of Service before enabling scraping.**
   The HTTP scraper rate-limits and sets an identifying User-Agent by default.

## Config

| Env var | Default | Meaning |
|---|---|---|
| `PRICEMON_INTERVAL_MIN` | 30 | Minutes between scheduled scrapes |
| `PRICEMON_NO_SCHEDULER` | — | Set to `1` to disable the background scheduler |

## Layout

```
config/competitors.yaml     competitor list + selectors
src/pricemon/
  scrapers/                 one adapter per store
  matching.py               fuzzy product matching
  pipeline.py               scrape -> store -> match
  queries.py                read side for the dashboard
  scheduler.py              periodic re-scrape
  api.py                    FastAPI app + dashboard
web/templates/dashboard.html
run.py                      CLI: scrape | match | serve
```
