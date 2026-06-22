# Deploying the live website (free, public URL)

The app is built to run as an always-on website: on startup it scrapes
immediately (so the page isn't blank), then re-scrapes every 30 minutes on its
own, and the dashboard live-updates in the browser. You just need to host it.

These steps put it online for free on **Render**. (Railway/Fly.io work the same
way — the `Procfile` and `render.yaml` are already included.)

## 1. The code is already on GitHub ✅

Private repo, already pushed:
**https://github.com/fjg00/noknok-price-monitor** (default branch `master`).

Nothing to do here unless you want to push later updates (see "Updating" below).

## 2. Deploy on Render (the only step that needs you)

Easiest — use the button in the [README](README.md#deploy-your-live-website-one-click),
or do it manually:

1. Sign up / log in at https://render.com using your **GitHub (fjg00)** account so
   Render can see the private repo.
2. Click **New +  ->  Blueprint**.
3. Select the `noknok-price-monitor` repo. Render reads [`render.yaml`](render.yaml)
   and configures everything (build, start command, Python 3.12, 30-min interval).
4. Click **Apply**. First build takes a few minutes.
5. You get a public URL like `https://noknok-price-monitor.onrender.com` — that's
   your live dashboard. Open it; the first scrape runs automatically on boot.

> Render needs you to authorize it against your GitHub account once — that's an
> account login only you can do, which is why this last step can't be automated.

## 3. (Recommended) Keep it awake 24/7

Render's **free** web service sleeps after ~15 minutes with no visitors, which
also pauses the 30-minute scraper. Two options:

- **Free fix:** create a free cron job at https://cron-job.org to GET your
  `https://<your-app>.onrender.com/healthz` every 10 minutes. That keeps the
  service awake so the scheduled scrapes keep firing.
- **Paid fix:** upgrade the Render service to the **Starter** plan (~$7/mo) — it
  never sleeps and gets a persistent disk (price history survives restarts).

> On the free plan the database is ephemeral: if the service restarts it loses
> history, but it re-scrapes fresh prices on boot, so the dashboard is never
> empty for long.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `PRICEMON_INTERVAL_MIN` | 30 | Minutes between automatic scrapes |
| `PORT` / `HOST` | injected | Set by the host; don't override |
| `PRICEMON_NO_SCHEDULER` | — | `1` disables the background scraper (testing) |

## Updating

Push to `master` and Render auto-redeploys:

```powershell
git add . ; git commit -m "update" ; git push
```

To change NokNok's own prices, edit [`data/noknok_prices.csv`](data/noknok_prices.csv)
and push. To add/adjust competitors, edit [`config/competitors.yaml`](config/competitors.yaml).
