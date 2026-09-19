"""GulogGratis.dk: dansk klassificeret-markedsplads, IKKE Schibsted-platformen
(anden DOM end dba.dk/blocket.se) -- egen React-app. Playwright headless,
throttlet, best-effort.

VIGTIGT (fundet ved research): søgeresultatsiden blander ægte private
annoncer med sponsorerede PriceRunner-"clickout"-links (nye produkter fra
webshops, ikke brugtmarked) -- disse identificeres og filtreres eksplicit fra
via deres `/clickout/`-href-præfiks, IKKE ved en pris- eller tekst-heuristik
som let kunne ramme forkert.

Fejler ALDRIG hele scriptet: bot-wall eller andre problemer logges og giver
blot en tom liste for denne kørsel.
"""

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.guloggratis")

BASE_URL = "https://www.guloggratis.dk"
SEARCH_URL_TMPL = BASE_URL + "/kategori/q-{query}"

BOT_WALL_MARKERS = ["captcha", "unusual traffic", "access denied", "er du en robot"]


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _parse_price(price_text: str):
    m = re.search(r"([\d\s.]+)\s*kr", price_text or "", re.I)
    if not m:
        return None, "DKK"
    amount_str = m.group(1).replace(" ", "").replace("\xa0", "").replace(".", "")
    try:
        return float(amount_str), "DKK"
    except ValueError:
        return None, "DKK"


def _parse_listing_cards(page):
    """Ægte annoncer: <a href="/annonce/<uuid>/<titel-slug>"> -- PRÆCIS 3
    "/"-tegn i href. "/annonce/opret"-knappen har kun 2. VERIFICERET mod
    reelt DOM 2026-09-19 (tidligere version af denne fil brugte fejlagtigt
    `<= 3` som afvisnings-tærskel, hvilket filtrerede ALLE rigtige annoncer
    fra -- rettet til `<= 2`).

    Der er INTET <article>-wrapper-element (modsat den oprindelige antagelse)
    -- <a> indeholder direkte <figure> (billede) + <header> med to <p>-tags
    (lokation, derefter pris) og <h4> (titel). Sponsorerede PriceRunner-
    "clickout"-links (/clickout/...) tælles ALDRIG med -- de er nye produkter
    fra webshops, ikke brugtmarkedet vi overvåger."""
    links = page.query_selector_all('a[href^="/annonce/"]')
    results = []
    for link in links:
        try:
            href = link.get_attribute("href") or ""
            if href.count("/") <= 2:  # /annonce/opret o.lign., ikke en rigtig annonce
                continue
            title_el = link.query_selector("h4")
            if not title_el:
                continue
            title = title_el.inner_text().strip()
            price_paragraphs = link.query_selector_all("header p")
            price_text = price_paragraphs[1].inner_text() if len(price_paragraphs) > 1 else ""
            url = href if href.startswith("http") else BASE_URL + href
            results.append({"title": title, "price_text": price_text, "url": url})
        except Exception:
            logger.exception("GulogGratis: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("GulogGratis: playwright er ikke installeret, springer kilden over")
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
                    logger.info("GulogGratis: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    try:
                        page.wait_for_selector('a[href^="/annonce/"]', timeout=6000)
                    except Exception:
                        pass

                    cards = _parse_listing_cards(page)
                    if not cards and _looks_like_bot_wall(page):
                        # Markører tjekkes KUN ved 0 kort -- se auktionshuset.py's
                        # tilsvarende kommentar for den konkrete falske positiv
                        # (indlejret captcha-script uden relation til blokering)
                        # dette forsvarer mod.
                        logger.warning("GulogGratis: bot-wall moedt for '%s', springer over", term)
                        break

                    for card in cards:
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
                                "origin_country_code": "DK",
                                "extra": {"search_term": term, "source_page": url},
                            }
                        )

                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception(
                        "GulogGratis: fejl under haandtering af '%s', springer over", term
                    )
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception("GulogGratis: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
