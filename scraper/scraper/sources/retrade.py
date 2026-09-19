"""Retrade.eu: nordisk B2B-auktionsplatform (dansk undersite /da). SSR HTML,
Playwright headless, throttlet, best-effort.

ÆRLIG FORVENTNING (fra research): domineret af tung entreprenør-/
landbrugsmaskineri -- 0 hits ved test-søgning på både "karcher" og
"støvsuger". Teknisk triviel og billig at inkludere (samme mønster som de
øvrige HTML-kilder), men forvent sjældne/ingen reelle fund for denne
varekategori. Inkluderet fordi brugeren bad om ALLE fundne auktionshuse, ikke
fordi der er dokumenteret markedsdækning her.

Priser er AKTUELT BUD (se pipeline.py's is_auction-nedgraderingslogik).
"""

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.retrade")

BASE_URL = "https://retrade.eu"
SEARCH_URL_TMPL = BASE_URL + "/da?search={query}&page=1"

BOT_WALL_MARKERS = ["captcha", "unusual traffic", "access denied"]


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _parse_price(price_text: str):
    m = re.search(r"([\d\s.,]+)\s*dkk", price_text or "", re.I)
    if not m:
        return None
    amount_str = m.group(1).replace(" ", "").replace("\xa0", "").replace(".", "").replace(",", "")
    try:
        return float(amount_str)
    except ValueError:
        return None


def _parse_listing_cards(page):
    cards = page.query_selector_all('a[href^="/da/auction/"]')
    results = []
    for card in cards:
        try:
            title_el = card.query_selector("h3")
            bid_el = card.query_selector("p.text-lg.font-bold")
            if not title_el or not bid_el:
                continue
            href = card.get_attribute("href") or ""
            url = href if href.startswith("http") else BASE_URL + href
            results.append(
                {
                    "title": title_el.inner_text().strip(),
                    "price_text": bid_el.inner_text().strip(),
                    "url": url,
                }
            )
        except Exception:
            logger.exception("Retrade: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Retrade: playwright er ikke installeret, springer kilden over")
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
                locale="da-DK",
            )
            page = context.new_page()

            pages_fetched = 0
            for term in search_terms:
                if pages_fetched >= max_pages:
                    break
                try:
                    url = _build_search_url(term)
                    logger.info("Retrade: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    try:
                        page.wait_for_selector('a[href^="/da/auction/"]', timeout=6000)
                    except Exception:
                        pass

                    cards = _parse_listing_cards(page)
                    if not cards and _looks_like_bot_wall(page):
                        # Markører tjekkes KUN ved 0 kort -- se auktionshuset.py's
                        # tilsvarende kommentar.
                        logger.warning("Retrade: bot-wall moedt for '%s', springer over", term)
                        break

                    for card in cards:
                        amount = _parse_price(card["price_text"])
                        if amount is None:
                            continue
                        raw_listings.append(
                            {
                                "title": card["title"],
                                "description": "",
                                "price_amount": amount,
                                "price_currency": "DKK",
                                "url": card["url"],
                                "origin_country_code": "DK",
                                "extra": {
                                    "search_term": term,
                                    "source_page": url,
                                    "is_auction": True,
                                },
                            }
                        )

                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception("Retrade: fejl under haandtering af '%s', springer over", term)
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception("Retrade: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
