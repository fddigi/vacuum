"""Klaravik.dk: dansk auktionsplatform for bygge-/erhvervsmaskiner (egen
DKK-visning, ikke bare en .se-visning). SSR HTML, Playwright headless,
throttlet, best-effort.

Priser her er AKTUELT BUD, ikke en fast pris -- se pipeline.py's
is_auction-nedgraderings-logik (kan aldrig blive "køb nu" alene på et
øjebliksbillede af buddet).
"""

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.klaravik")

BASE_URL = "https://www.klaravik.dk"
SEARCH_URL_TMPL = BASE_URL + "/auction/?searchtext={query}"

BOT_WALL_MARKERS = ["captcha", "unusual traffic", "access denied"]


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _parse_price(price_text: str):
    m = re.search(r"([\d\s.]+)\s*(?:dkk|kr)", price_text or "", re.I)
    if not m:
        return None
    amount_str = m.group(1).replace(" ", "").replace("\xa0", "").replace(".", "")
    try:
        return float(amount_str)
    except ValueError:
        return None


def _parse_listing_cards(page):
    cards = page.query_selector_all("article.product_card")
    results = []
    for card in cards:
        try:
            # VIGTIGT (fundet ved test 2026-09-19): Klaravik renderer ALLE
            # status-tags (ended/no-reserve/reserve-reached) i DOM'et for
            # HVERT kort samtidig, uanset faktisk status -- kun CSS skjuler de
            # irrelevante. `query_selector()` alene finder derfor ALTID
            # elementet (100% falsk positiv, filtrerede tidligere ALLE kort
            # fra), .is_visible() er nødvendigt for at skelne reelt afsluttet
            # fra blot tilstedeværende-men-skjult.
            ended_el = card.query_selector(".product_card__ended-tag")
            if ended_el and ended_el.is_visible():
                continue  # auktion reelt afsluttet -- ikke aktionabel
            link_el = card.query_selector('a[href*="/auction/product/"]')
            title_el = card.query_selector(".product_card__title")
            bid_el = card.query_selector(".product_card__current-bid")
            if not link_el or not title_el or not bid_el:
                continue
            href = link_el.get_attribute("href") or ""
            url = href if href.startswith("http") else BASE_URL + href
            location_el = card.query_selector(".product_card__info-text")
            results.append(
                {
                    "title": title_el.inner_text().strip(),
                    "price_text": bid_el.inner_text().strip(),
                    "url": url,
                    "location": location_el.inner_text().strip() if location_el else None,
                }
            )
        except Exception:
            logger.exception("Klaravik: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Klaravik: playwright er ikke installeret, springer kilden over")
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
                    logger.info("Klaravik: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    try:
                        page.wait_for_selector("article.product_card", timeout=6000)
                    except Exception:
                        pass

                    cards = _parse_listing_cards(page)
                    if not cards and _looks_like_bot_wall(page):
                        # Markører tjekkes KUN ved 0 kort -- se auktionshuset.py's
                        # tilsvarende kommentar.
                        logger.warning("Klaravik: bot-wall moedt for '%s', springer over", term)
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
                                    "location": card.get("location"),
                                    "is_auction": True,
                                },
                            }
                        )

                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception(
                        "Klaravik: fejl under haandtering af '%s', springer over", term
                    )
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception("Klaravik: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
