"""Auktionshuset dab A/S (auktionshuset.dk, kaldet "dab.dk" i den oprindelige
spec) -- dansk konkurs-/overskudsauktionshus. STÆRKESTE fund ved research:
reelt lager fra konkurs-/overskudsauktioner, ofte præcis den slags
professionelt udstyr specen leder efter (5 relevante Kärcher-våd/tørsugere
fundet ved test-søgning på "karcher").

SSR HTML, Playwright headless, throttlet, best-effort. Priser er AKTUELT BUD
(se pipeline.py's is_auction-nedgraderingslogik).
"""

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.auktionshuset")

BASE_URL = "https://www.auktionshuset.dk"
SEARCH_URL_TMPL = BASE_URL + "/lot/?search={query}"

# "captcha" er BEVIDST UDELADT: siden indlejrer permanent et reCAPTCHA-script
# til login-formularen i headeren på ALLE sider, uafhængigt af om søgningen gav
# reelle resultater eller ej -- markøren gav 100% falsk positiv ved test
# (0 kort + "captcha" fundet var simpelthen 0 reelle søgeresultater, ikke en
# blokering). Se fetch()'s "kun ved 0 kort"-logik for de resterende markører.
BOT_WALL_MARKERS = ["unusual traffic", "access denied"]

# NB: research fandt ingen dedikeret CSS-klasse for "auktion slut" på dette
# site (modsat Klaravik's .product_card__ended-tag) -- vi kan derfor IKKE
# eksplicit udelukke afsluttede auktioner her endnu. Ingen synlig ulempe
# observeret ved test (kun aktive lots dukkede op i søgeresultatet), men
# værd at revisitere hvis afsluttede lots begynder at optræde i praksis.


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _parse_price(price_text: str):
    m = re.search(r"([\d\s.,]+)", price_text or "")
    if not m:
        return None
    amount_str = m.group(1).replace(" ", "").replace("\xa0", "").replace(".", "").replace(",", ".")
    try:
        return float(amount_str)
    except ValueError:
        return None


def _parse_listing_cards(page):
    cards = page.query_selector_all("li.lot-item")
    results = []
    for card in cards:
        try:
            link_el = card.query_selector("a.flex.flex-col.flex-grow") or card.query_selector("a")
            if not link_el:
                continue
            title_el = link_el.query_selector("h3")
            bid_el = card.query_selector(".bid-amount")
            if not title_el or not bid_el:
                continue
            href = link_el.get_attribute("href") or ""
            url = href if href.startswith("http") else BASE_URL + href
            results.append(
                {
                    "title": title_el.inner_text().strip(),
                    "price_text": bid_el.inner_text().strip(),
                    "url": url,
                }
            )
        except Exception:
            logger.exception("Auktionshuset: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Auktionshuset: playwright er ikke installeret, springer kilden over")
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
                    logger.info("Auktionshuset: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    try:
                        page.wait_for_selector("li.lot-item", timeout=6000)
                    except Exception:
                        pass

                    cards = _parse_listing_cards(page)
                    if not cards and _looks_like_bot_wall(page):
                        # VIGTIGT (fundet ved test 2026-09-19): siden indlejrer et
                        # reCAPTCHA-script til login-formularen i headeren PÅ HVER
                        # SIDE, uanset søgning -- en naiv "captcha"-tekstscanning af
                        # HELE siden gav falsk positiv bot-wall selvom søgningen
                        # reelt gav gyldige resultater. Markørerne tjekkes derfor
                        # KUN når parsing allerede har givet 0 kort (ingen risiko for
                        # at fejlagtigt droppe en side der rent faktisk virkede).
                        logger.warning(
                            "Auktionshuset: bot-wall moedt for '%s', springer over", term
                        )
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
                    logger.exception(
                        "Auktionshuset: fejl under haandtering af '%s', springer over", term
                    )
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception(
            "Auktionshuset: kilden fejlede helt, springer kilden over for denne koersel"
        )
        return []

    return raw_listings
