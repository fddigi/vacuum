"""DBA.dk: Playwright headless, throttlet, best-effort. Ingen RSS -- søgninger
går til /recommerce/forsale/search, Schibsted-platformen (samme markup som
Blocket.se). Ported fra PASPEAKERS' sources/dba.py, uændret mønster.

Fejler ALDRIG hele scriptet: bot-wall eller andre problemer logges og giver
blot en tom liste for denne kørsel.

Opsamler siden 2026-10-03 et thumbnail pr. kort som `extra["image_url"]`
(nullable) -- den eneste af husets kilder der gør det. Se den udførlige,
live-målte kommentar over _IMAGE_SELECTORS for DOM-varianterne og for hvorfor
loading="lazy" her IKKE kræver scroll-triggering.

Opsamler stadig INGEN beskrivelse. Det er verificeret på ny 2026-10-03, ikke
antaget: søgeresultat-kortet indeholder kun pris, titel, lokation, dato og evt.
forhandlernavn, og sidens eneste strukturerede data (to application/ld+json-
blokke) sætter `"description"` til en ORDRET gentagelse af titlen for hver
annonce. En rigtig beskrivelse findes kun på selve annoncesiden og ville koste
én ekstra sideindlæsning pr. fund.
"""

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.dba")

BASE_URL = "https://www.dba.dk"
SEARCH_URL_TMPL = BASE_URL + "/recommerce/forsale/search?q={query}"

BOT_WALL_MARKERS = [
    "captcha",
    "for mange foresp",
    "unusual traffic",
    "access denied",
    "er du en robot",
]


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_bot_wall(page) -> bool:
    content = page.content().lower()
    return any(m in content for m in BOT_WALL_MARKERS)


# ---------------------------------------------------------------------------
# BILLED-URL PR. KORT (nyt 2026-10-03). Ingen af husets otte kilder opsamlede
# hidtil noget billede -- kun titel/pris/url. For fysiske varer hvor stand,
# stil og farve kun kan vurderes visuelt (brugerens konkrete opdrag: døre og
# vinduer til renoveringsprojektet) betyder det, at hver enkelt annonce skal
# åbnes manuelt for at kunne sorteres fra.
#
# DOM'et er MÅLT live mod dba.dk 2026-10-03 på 537 rigtige dør-/vinduesannoncer
# (10 søgeord). Der findes præcis TO kortvarianter, ingen andre:
#
#   1. FLERBILLED-KORT (401/537): en karrusel med ét <img> pr. billede, hvor
#      det synlige bærer klassen "sf-ad-carousel-desktop-item--active".
#      Alle de øvrige karrusel-billeder ligger i DOM'et samtidig, så et naivt
#      "første <img> i kortet" ville være tilfældigt rigtigt her og forkert
#      hvis DBA nogensinde ændrer rækkefølgen -- derfor matches --active
#      eksplicit FØRST. (Målt: --active var første <img> i alle 401 kort, men
#      det er en tilfældighed ved den nuværende rendering, ikke en kontrakt.)
#   2. ENKELTBILLED-KORT (133/537): ét <img> uden karrusel-klasserne.
#
#   3 af 537 kort havde slet INGEN <img> (annoncer uden uploadet billede).
#      Feltet er derfor nullable, og et manglende billede må aldrig få kortet
#      droppet -- samme best-effort-princip som resten af filen.
#
# src ER TIL STEDE I SSR-HTML'EN, OGSÅ UDEN SCROLL. Enkeltbilled-varianten har
# loading="lazy", hvilket ved første øjekast ser ud som lazy-loading der kræver
# scroll-triggering. Det gør det ikke: loading er kun et browser-HENT-hint,
# selve src-attributten står i den serverrenderede HTML. Målt eksplicit med en
# kørsel UDEN noget scroll: 54/54 kort havde src på begge søgeord. Derfor er
# der INGEN ændring i filens scroll-/ventelogik -- og derfor er data-src/
# srcset kun defensive fallbacks, ikke den forventede vej.
#
# Alle 534 observerede URL'er lå på images.dbastatic.dk (absolut https).
# Værten tjekkes BEVIDST ikke: et hårdt værtsfilter ville tavst nulstille
# feltet for alle kort, hvis DBA skifter CDN-domæne, og feltet er rent
# kosmetisk -- en forkert vært er langt billigere end et felt der holder op
# med at virke uden at nogen opdager det. Der kræves blot en absolut http(s)-
# URL, så en data:-placeholder (ikke observeret, men den klassiske lazy-load-
# teknik) ikke gemmes som et billede.
_IMAGE_SELECTORS = (
    "img.sf-ad-carousel-desktop-item--active",
    "img",
)


def _first_srcset_url(srcset: str | None) -> str | None:
    """Første URL i en srcset-liste ("<url> 240w, <url> 320w, ...").

    Kun fallback: 53 af 537 kort havde en srcset, og alle 53 havde OGSÅ en
    brugbar src. Den første kandidat er den mindste bredde (240w), hvilket er
    præcis det rigtige valg for et thumbnail.
    """
    for part in (srcset or "").split(","):
        url = part.strip().split(" ")[0].strip()
        if url.startswith("http"):
            return url
    return None


def _parse_image_url(card) -> str | None:
    """Thumbnail-URL for ét annonce-kort, eller None hvis annoncen ikke har
    noget billede. Se den lange kommentar ovenfor for de målte DOM-varianter."""
    for selector in _IMAGE_SELECTORS:
        el = card.query_selector(selector)
        if el is None:
            continue
        for attr in ("src", "data-src"):
            value = (el.get_attribute(attr) or "").strip()
            if value.startswith("http"):
                return value
        url = _first_srcset_url(el.get_attribute("srcset"))
        if url:
            return url
    return None


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
            results.append(
                {
                    "title": title,
                    "price_text": price_text,
                    "url": url,
                    "image_url": _parse_image_url(card),
                }
            )
        except Exception:
            logger.exception("DBA: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("DBA: playwright er ikke installeret, springer kilden over")
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
                    logger.info(
                        "DBA: naaet max_pages_total (%d), stopper for denne koersel", max_pages
                    )
                    break
                try:
                    url = _build_search_url(term)
                    logger.info("DBA: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    try:
                        page.wait_for_selector("article.sf-search-ad", timeout=6000)
                    except Exception:
                        pass

                    if _looks_like_bot_wall(page):
                        logger.warning(
                            "DBA: bot-wall/CAPTCHA moedt for '%s', springer kilden over",
                            term,
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
                                "origin_country_code": "DK",
                                "extra": {
                                    "search_term": term,
                                    "source_page": url,
                                    "image_url": card.get("image_url"),
                                },
                            }
                        )

                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception("DBA: fejl under haandtering af '%s', springer over", term)
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception("DBA: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
