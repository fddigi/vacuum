"""Kleinanzeigen.de: intet API, aggressiv bot-beskyttelse -> Playwright
headless, throttlet, best-effort. Ported fra PASPEAKERS' sources/kleinanzeigen.py,
samme frisk-browser-context-pr.-forespørgsel-mønster (se docstring i fetch()
for hvorfor en genbrugt context giver stille 0 resultater) -- men CSS-
selectorerne er FULDT OMSKREVET (fundet ved live-test 2026-09-19): sitet er
redesignet siden PASPEAKERS byggede sin version (`article.aditem`,
`.text-module-begin` osv. findes slet ikke længere i DOM'et).

TO kritiske fund fra denne test, begge rettet:
1. En obligatorisk GDPR-cookie-væg (#gdpr-banner-accept) blokerer AL
   resultat-rendering på hver eneste frisk browser-context, indtil den
   eksplicit klikkes væk -- uden dette får man ALTID 0 kort, permanent,
   uanset søgeterm (bekræftet: 22.247 reelle resultater for "kärcher", men 0
   `article.aditem`-elementer før klik).
2. Efter klik er selve resultat-listens struktur: `ul#srchrslt-adtable`
   indeholder `<li><article data-adid="...">`-kort. Titel er nu i et `<h3>`,
   pris i `<p class="text-title3 font-strong">`, og URL i article'ens
   `data-href`-attribut (relativ) -- verificeret 27/27 kort på en reel
   søgning, ingen fald tilbage til det gamle mønster.

Fejler ALDRIG hele scriptet: bot-wall eller andre problemer logges og giver
blot en tom liste for denne kørsel.
"""

import logging
import random
import re
import time
from urllib.parse import quote

from scraper_core.pricing import parse_price

logger = logging.getLogger("vacuum.kleinanzeigen")

BASE_URL = "https://www.kleinanzeigen.de"

BOT_WALL_MARKERS = ["captcha", "unusual traffic", "bot check", "access denied", "geo.captcha"]


def _build_search_url(term: str, page_num: int = 1) -> str:
    # KRITISK FUND (live-test 2026-09-19), TO LAG: søgeordet indgår her i
    # selve URL-STIEN (modsat dba.py/blocket.py/guloggratis.py, som sender
    # det som en query-parameter, hvor "/" er harmløst).
    # (1) `quote()`'s DEFAULT `safe="/"` lod et bogstaveligt "/" i søgeordet
    #     (fx modelnavne som "NT 35/1") passere UESCAPET, hvilket knækkede
    #     sti-strukturen og fik sitet til at falde tilbage til en generisk,
    #     urelateret resultatliste (50 fund om biler/lejligheder/hegn).
    # (2) Even et KORREKT escapet "/" (%2F) giver en hård 400 Bad Request på
    #     dette site -- stien kan slet ikke rumme tegnet i nogen form.
    # Løsning: erstat "/" med mellemrum (samme behandling som selve
    # mellemrummet lige efter) FØR quote() -- verificeret: "Kärcher NT 35/1"
    # -> "Kärcher-NT-35-1" giver 17 relevante fund, inkl. "Kärcher NT 35/1
    # Eco Te".
    query = quote(term.replace(" ", "-").replace("/", "-"))
    if page_num <= 1:
        return f"{BASE_URL}/s-{query}/k0"
    return f"{BASE_URL}/s-seite:{page_num}/{query}/k0"


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _dismiss_gdpr_banner(page) -> None:
    """Obligatorisk på HVER frisk context (se modulets docstring, fund #1) --
    uden dette klik forbliver resultatlisten permanent tom. Fejler stille hvis
    knappen ikke findes (allerede accepteret/banner ikke vist), aldrig en
    undtagelse op til kaldstedet."""
    try:
        btn = page.query_selector("#gdpr-banner-accept")
        if btn:
            btn.click()
            page.wait_for_timeout(1500)
    except Exception:
        logger.debug("Kleinanzeigen: intet GDPR-banner at afvise (eller allerede afvist)")


def _parse_price(price_text: str):
    m = re.search(r"([\d.,]+)\s*€", price_text or "")
    if not m:
        return None, "EUR"
    # decimal_style FORCED til "comma" (aldrig "auto") -- tysk talformat har
    # ingen selvafgørende signal for tusind-punktum vs. decimal-punktum.
    return parse_price(m.group(1), unit="major", decimal_style="comma"), "EUR"


def _parse_listing_cards(page):
    """Se modulets docstring, fund #2 for den fulde begrundelse for disse
    selectors (verificeret 27/27 kort på en reel søgning 2026-09-19)."""
    cards = page.query_selector_all("ul#srchrslt-adtable article[data-adid]")
    results = []
    for card in cards:
        try:
            title_el = card.query_selector("h3")
            price_el = card.query_selector("p.text-title3.font-strong")
            href = card.get_attribute("data-href")
            if not title_el or not href:
                continue
            title = title_el.inner_text().strip()
            price_text = price_el.inner_text().strip() if price_el else ""
            url = BASE_URL + href if href.startswith("/") else href
            results.append({"title": title, "price_text": price_text, "url": url})
        except Exception:
            logger.exception("Kleinanzeigen: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Kleinanzeigen: playwright er ikke installeret, springer kilden over")
        return []

    pw_cfg = config.get("playwright", {})
    min_delay = pw_cfg.get("min_delay_s", 3)
    max_delay = pw_cfg.get("max_delay_s", 8)
    max_pages_per_term = pw_cfg.get("max_pages_per_term", 3)
    max_pages_total = pw_cfg.get("max_pages_total", 30)
    headless = pw_cfg.get("headless", True)

    search_terms = config["search_terms"]["primary"] + config["search_terms"].get("secondary", [])
    raw_listings = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)

            pages_fetched_total = 0
            bot_wall_hit = False
            for term in search_terms:
                if bot_wall_hit:
                    break
                if pages_fetched_total >= max_pages_total:
                    logger.info(
                        "Kleinanzeigen: naaet max_pages_total (%d), stopper for denne koersel",
                        max_pages_total,
                    )
                    break

                for page_num in range(1, max_pages_per_term + 1):
                    if pages_fetched_total >= max_pages_total:
                        break

                    context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                        ),
                        viewport={"width": 1280, "height": 900},
                        locale="de-DE",
                    )
                    page = context.new_page()
                    try:
                        url = _build_search_url(term, page_num)
                        logger.info("Kleinanzeigen: henter '%s' side %d -> %s", term, page_num, url)
                        page.goto(url, timeout=20000)
                        pages_fetched_total += 1
                        _dismiss_gdpr_banner(page)

                        try:
                            page.wait_for_selector(
                                "ul#srchrslt-adtable article[data-adid]", timeout=6000
                            )
                        except Exception:
                            pass

                        cards = _parse_listing_cards(page)
                        if not cards:
                            # Markører tjekkes KUN ved 0 kort -- se
                            # auktionshuset.py's tilsvarende kommentar for den
                            # klasse falsk-positiv dette forsvarer mod.
                            if _looks_like_bot_wall(page):
                                logger.warning(
                                    "Kleinanzeigen: bot-wall for '%s' side %d, springer over",
                                    term,
                                    page_num,
                                )
                                bot_wall_hit = True
                            else:
                                logger.info(
                                    "Kleinanzeigen: '%s' side %d gav 0 kort, sidste side naaet",
                                    term,
                                    page_num,
                                )
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
                                    "origin_country_code": "DE",
                                    "extra": {"search_term": term, "source_page": url},
                                }
                            )

                        time.sleep(random.uniform(min_delay, max_delay))
                    except Exception:
                        logger.exception(
                            "Kleinanzeigen: fejl under haandtering af '%s' side %d, springer over",
                            term,
                            page_num,
                        )
                        break
                    finally:
                        context.close()

            browser.close()
    except Exception:
        logger.exception(
            "Kleinanzeigen: kilden fejlede helt, springer kilden over for denne koersel"
        )
        return []

    return raw_listings
