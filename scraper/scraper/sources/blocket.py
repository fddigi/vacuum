"""Blocket.se: samme Schibsted-platform/mønster som DBA -- Playwright
headless, throttlet, best-effort. Ported fra PASPEAKERS' sources/blocket.py.

Spec nævner Blocket specifikt for Skåne-regionen (tættest på Danmark) -- ingen
regional filtrering er implementeret her (Blockets søge-URL understøtter det
via /annonser/skane, men v1 søger hele Sverige og lader klassifikations-
scoring/prisloft filtrere i stedet, samme pragmatiske valg som seng-projektet
gør for DBA's brede søgninger).

Fejler ALDRIG hele scriptet: bot-wall eller andre problemer logges og giver
blot en tom liste for denne kørsel.
"""

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.blocket")

BASE_URL = "https://www.blocket.se"
SEARCH_URL_TMPL = BASE_URL + "/annonser/hela_sverige?q={query}"

BOT_WALL_MARKERS = [
    "captcha",
    "unusual traffic",
    "access denied",
    "are you a robot",
    "har vi upptaeckt",
]


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _parse_price(price_text: str):
    m = re.search(r"([\d\s]+)\s*kr", price_text or "", re.I)
    if not m:
        return None, "SEK"
    amount_str = m.group(1).replace(" ", "").replace("\xa0", "")
    try:
        return float(amount_str), "SEK"
    except ValueError:
        return None, "SEK"


def _parse_listing_cards(page):
    cards = page.query_selector_all("article.sf-search-ad")
    results = []
    for card in cards:
        try:
            title_el = card.query_selector("h2")
            link_el = card.query_selector("a.sf-search-ad-link")
            if not title_el or not link_el:
                continue
            title = title_el.inner_text().strip()
            price_el = card.query_selector(".font-bold")
            price_text = price_el.inner_text() if price_el else card.inner_text()
            url = link_el.get_attribute("href")
            results.append({"title": title, "price_text": price_text, "url": url})
        except Exception:
            logger.exception("Blocket: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Blocket: playwright er ikke installeret, springer kilden over")
        return []

    pw_cfg = config.get("playwright", {})
    min_delay = pw_cfg.get("min_delay_s", 3)
    max_delay = pw_cfg.get("max_delay_s", 8)
    max_pages = pw_cfg.get("max_pages_total", 30)
    headless = pw_cfg.get("headless", True)

    search_terms = config["search_terms"]["primary"] + config["search_terms"].get("secondary", [])
    raw_listings = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
                locale="sv-SE",
            )
            page = context.new_page()

            pages_fetched = 0
            for term in search_terms:
                if pages_fetched >= max_pages:
                    break
                try:
                    url = _build_search_url(term)
                    logger.info("Blocket: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    if _looks_like_bot_wall(page):
                        logger.warning(
                            "Blocket: bot-wall/CAPTCHA moedt for '%s', springer over", term
                        )
                        break

                    for card in _parse_listing_cards(page):
                        amount, currency = _parse_price(card["price_text"])
                        if amount is None:
                            continue
                        raw_listings.append(
                            {
                                "title": card["title"],
                                "description": "",
                                "price_amount": amount,
                                "price_currency": currency,
                                "url": card["url"],
                                "origin_country_code": "SE",
                                "extra": {"search_term": term, "source_page": url},
                            }
                        )

                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception("Blocket: fejl under haandtering af '%s', springer over", term)
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception("Blocket: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
