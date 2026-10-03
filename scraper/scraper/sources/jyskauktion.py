"""Jysk Auktion (jyskauktion.dk) -- jysk konkurs-/overskudsauktionshus, inkl.
bilauktion. SSR HTML, Playwright headless, throttlet, best-effort.

FUNDET af brugeren selv (2026-10-03): en konkret STØVSUGER-annonce fra "KONKURS
AUKTION OVER TIDL. TØMMERFIRMA" (katalog 313, produkt 74542, 50 kr. bud) --
samme kategori fund som auktionshuset.dk's oprindelige "stærkeste fund".

INGEN TEKST-SØGNING FUNGERER (verificeret live 2026-10-03): sitets søgeformular
(input[name=search-value], POST til /search/<term>) returnerer en tom
"Søgeord:"-header og 0 resultater for reelle, verificerede søgeord
("støvsuger"/"nilfisk"), selv når et matchende produkt beviseligt findes i en
aktiv katalog. Mulig årsag: søgningen kræver et samtidigt katalog-/auktions-
valg i stedet for fritekst alene, eller kræver JS-AJAX som Playwright's
form.submit()-emulering ikke trigger korrekt -- ikke undersøgt yderligere, da
alternativet er helt tilstrækkeligt:

STRATEGI: GENNEMBLADR i stedet for at søge. Forsiden lister de AKTUELT aktive
auktions-kataloger som `/catalog/<id>`-links (katalog-ID'er roterer når en
auktion slutter og en ny starter -- opdages derfor dynamisk hver kørsel, aldrig
hardkodet). Hvert katalog er sideopdelt (`/catalog/<id>/<side>/`, ~42 produkter
pr. side, antal sider ses i sidens egne `.pages`-links). Alle sider i alle
aktive kataloger gennemløbes -- IKKE et søgeord-loop som de øvrige kilder,
search_terms er derfor bevidst uden betydning for denne kilde (se fetch()'s
signatur, som stadig tager `config` for ensartethed, men ikke læser
search_terms derfra). Klassificeringen (normalize.py/classify.py) filtrerer
støjen fra bagefter, samme princip som klaravik.dk/auktionshuset.dk's brede
`per_source`-søgeord.

Priser er AKTUELT BUD (se pipeline.py's is_auction-nedgraderingslogik) --
".productBid" indeholder både DKK og EUR, kun DKK-tallet bruges.
"""

from __future__ import annotations

import logging
import random
import re
import time

logger = logging.getLogger("vacuum.jyskauktion")

BASE_URL = "https://www.jyskauktion.dk"

BOT_WALL_MARKERS = ["captcha", "unusual traffic", "access denied"]

_PRICE_PATTERN = re.compile(r"([\d.,\s\xa0]+)\s*dkk", re.I)
_CATALOG_ID_PATTERN = re.compile(r"/catalog/(\d+)\b")


def _looks_like_bot_wall(page) -> bool:
    content = page.inner_text("body").lower()
    return any(m in content for m in BOT_WALL_MARKERS)


def _parse_price(price_text: str) -> float | None:
    m = _PRICE_PATTERN.search(price_text or "")
    if not m:
        return None
    amount_str = m.group(1).replace(" ", "").replace("\xa0", "").replace(".", "").replace(",", "")
    try:
        amount = float(amount_str)
    except ValueError:
        return None
    # "0 DKK" betyder "intet bud endnu", ikke en reel pris (samme fund som
    # retrade.py/auktionshuset.py's tilsvarende auktionskilder).
    return amount if amount > 0 else None


def _discover_active_catalog_ids(page) -> list[str]:
    page.goto(BASE_URL + "/", timeout=20000)
    page.wait_for_timeout(1500)
    links = page.query_selector_all('a[href*="/catalog/"]')
    ids: list[str] = []
    for link in links:
        href = link.get_attribute("href") or ""
        m = _CATALOG_ID_PATTERN.search(href)
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


def _page_count(page) -> int:
    """Antal sider i det AKTUELT viste katalog, aflæst fra .pages-linkene
    (fx '1 - 42' / '213 - 238' per side) -- mindst 1, selv hvis et lille
    katalog slet ikke viser pagineringslinks.

    KRITISK FUND (live-test 2026-10-04): siden gentager HELE paginerings-
    widget'en to gange pr. side (en kopi over og under produktgitteret) --
    et naivt `len(links)` talte derfor dobbelt (8 i stedet for 4 reelle
    sider for et katalog med 191 produkter). Dedupliceres på selve href'en."""
    links = page.query_selector_all(".pages a")
    unique_hrefs = {link.get_attribute("href") for link in links}
    return max(len(unique_hrefs), 1)


def _parse_listing_cards(page) -> list[dict]:
    cards = page.query_selector_all(".product-holder")
    results = []
    for card in cards:
        try:
            desc_el = card.query_selector(".productDescription .text")
            bid_el = card.query_selector(".productBid")
            if not desc_el or not bid_el:
                continue
            product_id = (card.get_attribute("id") or "").removeprefix("product_")
            if not product_id:
                continue
            results.append(
                {
                    "title": desc_el.inner_text().strip(),
                    "price_text": bid_el.inner_text().strip(),
                    "url": f"{BASE_URL}/product/{product_id}",
                }
            )
        except Exception:
            logger.exception("Jysk Auktion: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Jysk Auktion: playwright er ikke installeret, springer kilden over")
        return []

    pw_cfg = config.get("playwright", {})
    min_delay = pw_cfg.get("min_delay_s", 3)
    max_delay = pw_cfg.get("max_delay_s", 8)
    max_pages = pw_cfg.get("max_pages_total", 30)
    headless = pw_cfg.get("headless", True)

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

            try:
                catalog_ids = _discover_active_catalog_ids(page)
            except Exception:
                logger.exception("Jysk Auktion: kunne ikke hente forsiden, springer kilden over")
                catalog_ids = []
            logger.info(
                "Jysk Auktion: %d aktiv(e) katalog(er) fundet: %s", len(catalog_ids), catalog_ids
            )

            # KRITISK FUND (live-test 2026-10-04): et enkelt stort katalog
            # (bilauktionen, 311, fire reelle sider efter _page_count-fixet
            # ovenfor -- men andre kataloger kan være større) kan ellers
            # opbruge HELE max_pages_total alene, hvis det ligger først i
            # opdagelsesordenen, og dermed udelukke resten af kataloger den
            # samme kørsel -- herunder det katalog brugerens eget fund
            # (støvsuger, katalog 313) lå i. Budgettet deles derfor LIGELIGT
            # mellem de opdagede kataloger på forhånd, uanset rækkefølge.
            catalog_budget = max(1, max_pages // max(len(catalog_ids), 1))

            pages_fetched = 0
            for catalog_id in catalog_ids:
                if pages_fetched >= max_pages:
                    break
                catalog_pages_fetched = 0
                try:
                    url = f"{BASE_URL}/catalog/{catalog_id}/0/"
                    logger.info("Jysk Auktion: henter katalog %s -> %s", catalog_id, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1
                    catalog_pages_fetched += 1

                    try:
                        page.wait_for_selector(".product-holder", timeout=6000)
                    except Exception:
                        pass

                    # Side 0 er allerede hentet ovenfor (bruges også til at
                    # aflæse total_pages) -- loopet starter derfor ved 0, men
                    # springer selve goto() for netop den side over.
                    total_pages = _page_count(page)
                    for page_index in range(total_pages):
                        if page_index > 0:
                            if (
                                pages_fetched >= max_pages
                                or catalog_pages_fetched >= catalog_budget
                            ):
                                break
                            page_url = f"{BASE_URL}/catalog/{catalog_id}/{page_index}/"
                            page.goto(page_url, timeout=20000)
                            pages_fetched += 1
                            catalog_pages_fetched += 1
                            try:
                                page.wait_for_selector(".product-holder", timeout=6000)
                            except Exception:
                                pass

                        cards = _parse_listing_cards(page)
                        if not cards and _looks_like_bot_wall(page):
                            logger.warning(
                                "Jysk Auktion: bot-wall moedt for katalog %s side %d, springer "
                                "resten af kataloget over",
                                catalog_id,
                                page_index,
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
                                        "search_term": f"katalog-{catalog_id}",
                                        "source_page": url,
                                        "is_auction": True,
                                    },
                                }
                            )

                        time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception(
                        "Jysk Auktion: fejl under haandtering af katalog %s, springer over",
                        catalog_id,
                    )
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception(
            "Jysk Auktion: kilden fejlede helt, springer kilden over for denne koersel"
        )
        return []

    return raw_listings
