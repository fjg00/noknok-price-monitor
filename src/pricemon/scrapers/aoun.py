"""Aoun (Le Charcutier) scraper — authenticated headless browser.

Le Charcutier renders its catalog client-side AND only shows prices to
logged-in users (anonymous visitors see products but no prices). So this
scraper drives a real headless browser: it logs in with your account, then
walks each /shop/<category> page and reads the live prices.

Prices on the site are in Lebanese Pounds (L.L). To compare against NokNok's
USD prices we convert with `lbp_per_usd` from competitors.yaml (market rate).

Setup:
  1. Create an account on https://www.lecharcutier.com
  2. setx AOUN_USERNAME "you@email.com"   /   setx AOUN_PASSWORD "your-password"
  3. In competitors.yaml set aoun `enabled: true`, list `categories`, and set
     `lbp_per_usd` to the current rate.
  4. python run.py test aoun
"""
from __future__ import annotations

import os
import re

from .base import BaseScraper, ScrapedProduct

_LL_RE = re.compile(r"([\d][\d.,]*)\s*L\.?\s*L", re.IGNORECASE)
BASE = "https://www.lecharcutier.com"


class AounScraper(BaseScraper):
    DEFAULT_LBP_PER_USD = 89500  # update via config; ~market rate

    def scrape(self, categories: list[str]) -> list[ScrapedProduct]:
        from playwright.sync_api import sync_playwright

        user = os.getenv("AOUN_USERNAME")
        pwd = os.getenv("AOUN_PASSWORD")
        if not (user and pwd):
            raise RuntimeError(
                "Aoun is enabled but AOUN_USERNAME / AOUN_PASSWORD are not set. "
                "Le Charcutier only shows prices to logged-in accounts."
            )

        cats = self.cfg.selectors.get("categories") or categories
        rate = float(self.cfg.selectors.get("lbp_per_usd", self.DEFAULT_LBP_PER_USD))
        out: list[ScrapedProduct] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                locale="en-US",
            )
            page = ctx.new_page()
            if not self._login(page, user, pwd):
                browser.close()
                raise RuntimeError(
                    "[aoun] login failed — check AOUN_USERNAME/AOUN_PASSWORD. "
                    "If credentials are correct, the login form selectors may have changed."
                )

            for cat in cats:
                out.extend(self._scrape_category(page, cat, rate))
            browser.close()
        return out

    def _login(self, page, user: str, pwd: str) -> bool:
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)
        try:
            # Username field: the text/email/tel input asking for mobile or email.
            page.fill(
                "input[placeholder*='mobile' i], input[placeholder*='email' i], "
                "input[name='login_email'], input[name='login_username']",
                user,
            )
            page.fill("#login_password, input[name='login_password']", pwd)
            # Submit: a button/link labelled Login / Sign In near the form.
            for sel in ("button:has-text('Login')", "button:has-text('Sign In')",
                        "button[type='submit']", "input[type='submit']"):
                if page.locator(sel).count():
                    page.locator(sel).first.click()
                    break
            page.wait_for_timeout(3500)
        except Exception as exc:
            print(f"[aoun] login interaction failed: {exc}")
            return False
        # Logged in if a logout/profile affordance is present or login form is gone.
        html = page.content().lower()
        return ("logout" in html) or ("my account" in html) or ("login_password" not in html)

    def _scrape_category(self, page, cat: str, rate: float) -> list[ScrapedProduct]:
        url = f"{BASE}/shop/{cat}"
        try:
            page.goto(url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(2000)
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(2500)
        except Exception as exc:
            print(f"[aoun] failed to load {url}: {exc}")
            return []

        rows = page.evaluate(
            r"""() => {
              const links=[...document.querySelectorAll('.filter_data a[href*="/shop/"]')]
                .filter(a=>/\/\d+-/.test(a.href) && !a.closest('.owl-item'));
              const seen=new Set(); const out=[];
              for(const a of links){
                const href=a.href; if(seen.has(href))continue; seen.add(href);
                let card=a;
                for(let i=0;i<6;i++){ if(card.parentElement && !/L\.?\s*L/i.test(card.innerText)) card=card.parentElement; else break; }
                const m=card.innerText.replace(/\s+/g,' ').match(/([\d][\d.,]*)\s*L\.?\s*L/i);
                out.push({href, name:(a.getAttribute('title')||a.innerText||'').replace(/\s+/g,' ').trim(), priceText:m?m[1]:null});
              }
              return out;
            }"""
        )

        out: list[ScrapedProduct] = []
        for r in rows:
            if not r.get("priceText"):
                continue  # no price visible (not logged in, or item unpriced)
            lbp = float(r["priceText"].replace(",", "").replace(".", "")) if r["priceText"] else None
            if not lbp:
                continue
            usd = round(lbp / rate, 2)
            slug = r["href"].rstrip("/").split("/")[-1][:80]
            out.append(
                ScrapedProduct(
                    external_id=f"{self.key}-{slug}"[:128],
                    name=r["name"][:200],
                    price=usd,
                    currency="USD",
                    category=cat,
                    url=r["href"],
                )
            )
        if not out:
            print(f"[aoun] no priced products in '{cat}'. If you ARE logged in, the "
                  f"price selector may need adjusting for this category.")
        return out
