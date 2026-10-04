"""Genbyg.dk -- "Danmarks største webshop for brugte byggematerialer".
Ren SSR HTML via almindelige HTTP-requests (IKKE Playwright -- siden kræver
intet JS for selve søgeresultaterne, verificeret ved plain curl 2026-10-04).

FØRSTE KATEGORI-2-KILDE (døre/vinduer, se categories.py). Fundet og grundigt
undersøgt af en Opus-research-opgave 2026-10-04 (se README's SHV-afsnit).

HVORFOR POST /rest/search OG IKKE GET /soeg/: begge ruter returnerer samme
kort-markup, men kun POST-ruten respekterer specWidth/specHeight-felterne.
Målt: `q=branddør` via GET -> 54 (uændret selv med specWidth=89 tilføjet);
samme forespørgsel via POST -> 39 når specWidth/specHeight sættes. Denne
kilde sender BEVIDST ALDRIG specWidth/specHeight -- Genbygs eget filter er
et ±~10 cm-tolerancebånd omkring ÉT centrum, uegnet til en bred scraper der
skal finde ALLE mål og lade brugeren selv filtrere bagefter (det er selve
pointen med denne kategori: DBA kan ikke filtrere på mål, Genbyg kan, men vi
henter bredt og filtrerer i dashboardet for at undgå at skulle gætte ét
"rigtigt" mål pr. søgning).

STRUKTURERET DATA PR. KORT (ikke tekstudtræk): hvert søgeresultat-kort har
egne Bredde:/Højde:/Tykkelse:-felter i cm, varenummer, og pris -- langt mere
pålideligt end at udtrække mål fra en fritekst-titel (se doere_normalize.py's
docstring for hvordan disse to kilde-typer (struktureret vs. fritekst)
håndteres under samme kontrakt).

KATEGORI-BROWSE VIRKER IKKE: selve kategorisiderne
(/doere-vinduer/brugte-doere/branddoere/...) er client-side renderet (0 kort
i rå HTML) -- søgeruten er den eneste der virker for en scraper uden
browser-JS-eksekvering.

Prisfeltet bruger dansk tusind-/decimalnotation omvendt af hvad man skulle
tro ved første øjekast: "1.500,00" er ET TUSIND FEM HUNDREDE, ikke 1,5 --
punktum er tusindseparator, komma er decimal. Samme konvention for mål
("92,70 cm" = 92,7 cm, ikke 9270).
"""

from __future__ import annotations

import logging
import random
import re
import time

import requests

logger = logging.getLogger("vacuum.genbyg")

BASE_URL = "https://genbyg.dk"
SEARCH_URL = BASE_URL + "/rest/search"

_PRICE_PATTERN = re.compile(r"([\d.]+,\d{2})")
_SPEC_PATTERN = re.compile(r"(Bredde|Højde|Tykkelse):\s*([\d.]+,\d+)\s*cm", re.I)


def _danish_decimal_to_float(text: str) -> float | None:
    """'1.500,00' / '92,70' -- punktum er tusindseparator, komma er decimal."""
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_price(price_text: str) -> float | None:
    m = _PRICE_PATTERN.search(price_text or "")
    if not m:
        return None
    return _danish_decimal_to_float(m.group(1))


def _parse_specs(specs_text: str) -> dict:
    """Udtrækker Bredde/Højde/Tykkelse (cm) fra kortets egne specs-felter --
    IKKE fritekst-gætteri, se modulets docstring."""
    attributes: dict = {}
    key_map = {"bredde": "width_cm", "højde": "height_cm", "tykkelse": "thickness_cm"}
    for label, value in _SPEC_PATTERN.findall(specs_text or ""):
        key = key_map.get(label.lower())
        parsed = _danish_decimal_to_float(value)
        if key and parsed is not None:
            attributes[key] = parsed
    return attributes


def _parse_listing_cards(html: str) -> list[dict]:
    """Parser kort-markup med regex, ikke en DOM-parser -- siden er ren SSR
    HTML uden Playwright i spil her, og kortstrukturen er regelmæssig nok
    (verificeret mod 24+ rigtige kort) at et par målrettede regex er
    tilstrækkeligt uden at tilføje en HTML-parser-afhængighed for én kilde."""
    results = []
    card_pattern = re.compile(
        r'data-product-url="(?P<url>[^"]+)".*?'
        r'product-list__item__name">(?P<title>[^<]+)</h2>.*?'
        r"Varenr\.:\s*(?P<varenr>\d+)\s*</span>"
        r"(?P<specs>.*?)</ul>.*?"
        r'product-list__item__price__current">\s*(?P<price>[^<]+?)\s*(?:pr\.|<)',
        re.S,
    )
    for m in card_pattern.finditer(html):
        results.append(
            {
                "title": m.group("title").strip(),
                "url": BASE_URL + m.group("url"),
                "varenr": m.group("varenr"),
                "specs_text": m.group("specs"),
                "price_text": m.group("price"),
            }
        )
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    pw_cfg = config.get("playwright", {})
    min_delay = pw_cfg.get("min_delay_s", 3)
    max_delay = pw_cfg.get("max_delay_s", 8)
    max_pages = pw_cfg.get("max_pages_total", 30)

    search_terms = config["search_terms"]["primary"] + config.get("search_terms", {}).get(
        "secondary", []
    )
    raw_listings = []
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
    )

    pages_fetched = 0
    for term in search_terms:
        if pages_fetched >= max_pages:
            break
        try:
            page_num = 1
            while pages_fetched < max_pages:
                logger.info("Genbyg: henter '%s' side %d", term, page_num)
                resp = session.post(SEARCH_URL, data={"q": term, "page": page_num}, timeout=20)
                pages_fetched += 1
                if resp.status_code != 200:
                    logger.warning(
                        "Genbyg: uventet status %d for '%s' side %d",
                        resp.status_code,
                        term,
                        page_num,
                    )
                    break

                cards = _parse_listing_cards(resp.text)
                if not cards:
                    break

                for card in cards:
                    amount = _parse_price(card["price_text"])
                    if amount is None:
                        continue
                    attributes = _parse_specs(card["specs_text"])
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
                                "source_page": SEARCH_URL,
                                "varenr": card["varenr"],
                                "attributes": attributes,
                            },
                        }
                    )

                # Genbyg returnerer 24 kort pr. side -- færre end 24 betyder
                # sidste side (samme "stop ved tom/delvis side"-princip som
                # jyskauktion.py's katalog-paginering).
                if len(cards) < 24:
                    break
                page_num += 1
                time.sleep(random.uniform(min_delay, max_delay))
        except Exception:
            logger.exception("Genbyg: fejl under haandtering af '%s', springer over", term)
            continue

    return raw_listings
