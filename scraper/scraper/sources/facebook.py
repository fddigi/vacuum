"""Facebook Marketplace: SSR HTML via en logget-ind Playwright-session,
throttlet, best-effort.

BEVIDST SPRUNGET OVER TIDLIGT I PROJEKTET (se README's "BEVIDST UDELADT"-
afsnit fra opstarten) -- høj ToS-/bot-detektions-risiko, og kræver login,
modsat alle øvrige syv kilder som scrapes helt anonymt. Genoptaget 2026-09-30
efter brugeren selv observerede flere relevante annoncer der, som scraperens
øvrige kilder aldrig ville finde (Facebook Marketplace-annoncer indekseres
ikke af nogen af de andre platforme).

RISIKOMODEL -- læs dette før du ændrer noget her:
  * Kræver to session-cookies (c_user + xs) fra en RIGTIG, logget-ind konto.
    Brugeren har bevidst oprettet en DEDIKERET Firefox-profil til formålet,
    IKKE deres primære konto -- præcis den forholdsregel der gør dette
    acceptabelt at bygge. Cookies ligger i .env (FACEBOOK_C_USER/
    FACEBOOK_XS), git-ignoreret, ALDRIG i denne fil eller i config.yaml.
  * Facebooks vilkår forbyder eksplicit automatiseret dataindsamling. Sessionen
    kan blive spærret uden varsel -- det er ikke en fejl i denne kode, hvis
    det sker, blot en realiseret og accepteret risiko.
  * Kilden fejler GRACEFULT hvis cookies mangler (kilden er slået fra i
    config.yaml pr. default, se dér) eller sessionen er udløbet/spærret
    (session_invalid-detektion nedenfor, samme "kun ved 0 kort"-forsigtighed
    som bot-wall-tjek i de øvrige kilder) -- aldrig en hård fejl der vælter
    resten af kørslen.

KENDT BEGRÆNSNING: Marketplace er RADIUS-baseret omkring kontoens registrerede
lokation (auto-redirected til "/marketplace/copenhagen/..." for denne konto
ved test), IKKE landsdækkende som dba.dk/blocket.se. Sjællandske/hovedstads-
fund er derfor overrepræsenteret; jysk/fynsk udbud kan mangle helt. Ingen kendt
måde at udvide radius uden en UI-interaktion pr. søgning (dyrere, ikke
implementeret i v1).

VERIFICERET LIVE 2026-09-30 (mod brugerens egen konto): reelle, relevante fund
allerede på simple søgeord, bl.a. "Metabo industristøvsuger ASA 30 H PC" og
"STARMIX Industristøvsuger 1420 Energetic \"H\"" -- begge allerede i vores
egen model-whitelist (models.py).

SELEKTOR-STRATEGI: Facebooks CSS-klasser er fuldstændig obfuskerede
("x1i10hfl xjbqb8w ..."), ustabile på tværs af sessioner/AB-tests, og ubrugelige
som selector. Hvert annonce-kort ligger derimod som en <a href="/marketplace/
item/<id>/...">, og selve <a>-tagget bærer et STRUKTURERET, menneskelæsbart
aria-label (tilgængeligheds-tekst, langt mere stabilt end CSS):
    "<titel>, <pris> kr[, reduceret fra <gammel pris> kr], <lokation>, opslag <id>"
Titel og lokation kan begge indeholde kommaer (flerords-lokationer som
"Strøby Egede, Roskilde, Denmark", flerlinjede titler) -- parses derfor med et
ét-shot regex der ankrer på de to entydige dele (", <tal> kr" og ", opslag
<tal>$"), ikke en naiv split(","). Se _parse_card().
"""

from __future__ import annotations

import logging
import random
import re
import time
from urllib.parse import quote

logger = logging.getLogger("vacuum.facebook")

BASE_URL = "https://www.facebook.com"
SEARCH_URL_TMPL = BASE_URL + "/marketplace/search/?query={query}"

# Facebooks EU/DMA-samtykkeflow ("Du skal træffe et valg om Marketplace") og
# den almindelige login-side er begge tegn på at sessionen IKKE er brugbar --
# enten cookies er udløbet/spærret, eller kontoen aldrig har gennemført
# engangs-samtykket manuelt (se facebook_config.py's docstring). Tjekkes KUN
# ved 0 kort, samme forsigtighedsprincip som de øvrige kilders bot-wall-tjek
# (undgår falsk positiv hvis login-markup blot findes et sted i DOM'et uden at
# reelt blokere resultaterne).
SESSION_INVALID_MARKERS = [
    "du skal træffe et valg om marketplace",
    "log på facebook",
    "you must log in to continue",
]

_ARIA_LABEL_PATTERN = re.compile(
    r"^(?P<title>.+?),\s*(?P<price>[\d.,\s\xa0]+)\s*kr"
    r"(?:,\s*reduceret fra\s*[\d.,\s\xa0]+\s*kr)?"
    r",\s*(?P<location>.+?),\s*opslag\s*(?P<item_id>\d+)$",
    re.I | re.S,
)


def _build_search_url(term: str) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term))


def _looks_like_session_invalid(page) -> bool:
    content = page.inner_text("body").lower()
    return any(m in content for m in SESSION_INVALID_MARKERS)


def _parse_price(price_text: str) -> float | None:
    amount_str = (price_text or "").replace(" ", "").replace("\xa0", "").replace(".", "")
    amount_str = amount_str.replace(",", ".")
    try:
        return float(amount_str)
    except ValueError:
        return None


def _parse_card(aria_label: str) -> dict | None:
    """Parser ét kort-links aria-label til title/price_amount/url -- se
    modulets docstring for hvorfor aria-label og ikke CSS-selectors."""
    if not aria_label:
        return None
    m = _ARIA_LABEL_PATTERN.match(aria_label.strip())
    if not m:
        return None
    price = _parse_price(m.group("price"))
    if price is None:
        return None
    title = re.sub(r"\s+", " ", m.group("title")).strip()
    return {
        "title": title,
        "price_amount": price,
        "url": f"{BASE_URL}/marketplace/item/{m.group('item_id')}/",
        "location": re.sub(r"\s+", " ", m.group("location")).strip(),
    }


def _parse_listing_cards(page) -> list[dict]:
    links = page.query_selector_all('a[href*="/marketplace/item/"]')
    results = []
    for link in links:
        try:
            parsed = _parse_card(link.get_attribute("aria-label"))
            if parsed is not None:
                results.append(parsed)
        except Exception:
            logger.exception("Facebook: kunne ikke parse et annonce-kort, springer over")
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    from .. import facebook_config

    settings = facebook_config.get_facebook_settings()
    if not settings.configured:
        logger.info(
            "Facebook: FACEBOOK_C_USER/FACEBOOK_XS ikke sat i .env, springer kilden over "
            "(se sources/facebook.py's docstring for hvordan de tilføjes)"
        )
        return []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Facebook: playwright er ikke installeret, springer kilden over")
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
            context.add_cookies(
                [
                    {
                        "name": "c_user",
                        "value": settings.facebook_c_user,
                        "domain": ".facebook.com",
                        "path": "/",
                    },
                    {
                        "name": "xs",
                        "value": settings.facebook_xs,
                        "domain": ".facebook.com",
                        "path": "/",
                    },
                ]
            )
            page = context.new_page()

            pages_fetched = 0
            for term in search_terms:
                if pages_fetched >= max_pages:
                    break
                try:
                    url = _build_search_url(term)
                    logger.info("Facebook: henter '%s' -> %s", term, url)
                    page.goto(url, timeout=20000)
                    pages_fetched += 1

                    try:
                        page.wait_for_selector('a[href*="/marketplace/item/"]', timeout=6000)
                    except Exception:
                        pass

                    cards = _parse_listing_cards(page)
                    if not cards and _looks_like_session_invalid(page):
                        logger.warning(
                            "Facebook: session ugyldig/udløbet ved '%s' (login- eller "
                            "samtykke-skærm mødt) -- springer resten af kilden over denne "
                            "kørsel. Se sources/facebook.py's docstring for gentræk af cookies.",
                            term,
                        )
                        break

                    for card in cards:
                        raw_listings.append(
                            {
                                "title": card["title"],
                                "description": "",
                                "price_amount": card["price_amount"],
                                "price_currency": "DKK",
                                "url": card["url"],
                                "origin_country_code": "DK",
                                "extra": {
                                    "search_term": term,
                                    "source_page": url,
                                    "location": card["location"],
                                },
                            }
                        )

                    time.sleep(random.uniform(min_delay, max_delay))
                except Exception:
                    logger.exception(
                        "Facebook: fejl under haandtering af '%s', springer over", term
                    )
                    continue

            context.close()
            browser.close()
    except Exception:
        logger.exception("Facebook: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
