"""Skave Nedbrydning (skave-nedbrydning.dk, Holstebro) -- det største udbud
af genbrugs-byggematerialer i en dedikeret Opus-undersøgelse af 16 kandidat-
sites (research/byggematerialer-kilder-2026-10-10.md, afsnit 2-3): 5.447
varer i alt, 2.914 vinduer alene. Ren SSR HTML (OpenCart), ingen bot-
beskyttelse, INGEN Playwright nødvendig -- verificeret live, plain `requests`
giver fuld HTML i første forsøg.

OBLIGATORISK 30-SEKUNDERS THROTTLING (IKKE valgfrit): sitets EGEN robots.txt
kræver `Crawl-delay: 30` og forbyder eksplicit `?limit=`/`?sort=`/`?order=`
(ellers kunne hele kataloget hentes på 11 requests med `?limit=500` i stedet
for ~100+ sider á 40 kort). Denne kilde respekterer begge dele -- IKKE en
teknisk begrænsning, en EKSPLICIT regel fra sitet selv. En kørsel af alle
relevante kategorier tager derfor typisk 15-45+ minutter; se
`sources_min_interval_hours` i config.doere.yaml for hvorfor denne kilde
IKKE bør køre hver eneste scraper-cyklus.

STRUKTURERET DATA, BEDST I HELE UNDERSØGELSEN: hvert kort har sin egen
"infos"-blok med NAVNGIVNE felter -- "km" (karmdybde), "b" (bredde), "h"
(højde), "v" (VÆGT i kg, ingen anden kilde i undersøgelsen leverer dette).
Målt dækning: 100% i dør-/vinduekategorierne specifikt.

KATEGORIER (sitets egne URL-slugs, fundet ved at læse forsidens kategori-
navigation -- IKKE i den oprindelige URL brugeren sendte, som kun pegede på
"vinduer"): vinduer, specialvinduer, vinduer-m-et-lag-glas,
vinduer-ell-dore-blyindfattede (alle "vindue"-subtype), terrassedore
(terrassedør-subtype), dore-indvendige + dore-udvendige (generisk dør --
MÅLT FUND: rigtige branddøre ligger blandet ind imellem almindelige døre her
under dore-udvendige, ikke i en egen "branddøre"-kategori, fx "Branddør --
Daloc S30 EL30" -- fire_rating-tekstudtrækket i doere_normalize.py fanger
dem alligevel uden en kategori-hint for selve branddør-bøtten).

Dansk tal-notation som genbyg.dk: punktum er tusindseparator, komma er
decimal ("1.000,00" = et tusind kr, "285,0" cm = 285,0 cm).
"""

from __future__ import annotations

import logging
import re
import time

import requests

logger = logging.getLogger("vacuum.skave_nedbrydning")

BASE_URL = "https://www.skave-nedbrydning.dk"

# category-slug -> subtype_hint (se doere_normalize.classify_subtype()).
_CATEGORY_SLUGS = {
    "vinduer": "vindue",
    "specialvinduer": "vindue",
    "vinduer-m-et-lag-glas": "vindue",
    "vinduer-ell-dore-blyindfattede": "vindue",
    "terrassedore": "terrassedoer",
    "dore-indvendige": "doer_andet",
    "dore-udvendige": "doer_andet",
}

_PRICE_PATTERN = re.compile(r"([\d.]+,\d{2})\s*<span class=\"currency-symbol\">")
_INFOS_PATTERN = re.compile(r"<strong>(km|b|h|v)</strong>:\s*([\d.,]+)\s*(?:cm|kg)?\s*<br", re.I)
_CARD_PATTERN = re.compile(
    r'<div class="product-grid.*?'
    r'<a href="(?P<url>https://www\.skave-nedbrydning\.dk/vareliste/[^"]+)">.*?'
    r'<div class="name">(?P<title>[^<]+)</div>\s*'
    r'(?:<div class="description">\s*(?P<desc>.*?)\s*</div>)?.*?'
    r'<div class="infos[^"]*">(?P<infos>.*?)</div>.*?'
    + _PRICE_PATTERN.pattern,
    re.S,
)


def _danish_decimal_to_float(text: str) -> float | None:
    cleaned = text.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_infos(infos_text: str) -> dict:
    attributes: dict = {}
    key_map = {"b": "width_cm", "h": "height_cm", "km": "thickness_cm"}
    for label, value in _INFOS_PATTERN.findall(infos_text or ""):
        key = key_map.get(label.lower())
        parsed = _danish_decimal_to_float(value)
        if key and parsed is not None:
            attributes[key] = parsed
    return attributes


def _parse_cards(html: str) -> list[dict]:
    results = []
    for m in _CARD_PATTERN.finditer(html):
        # Prisen hentes via et separat opslag i stedet for _CARD_PATTERN's
        # egen indlejrede gruppe, for robusthed mod gruppenummer-forskydning
        # hvis mønsteret ændres senere.
        price_match = re.search(r"([\d.]+,\d{2})\s*<span class=\"currency-symbol\"", m.group(0))
        price = _danish_decimal_to_float(price_match.group(1)) if price_match else None
        results.append(
            {
                "title": m.group("title").strip(),
                "description": (m.group("desc") or "").strip(),
                "url": m.group("url"),
                "infos_text": m.group("infos"),
                "price": price,
            }
        )
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    pw_cfg = config.get("playwright", {})
    # 30s er IKKE en default man kan justere ned -- se modulets docstring.
    # Tillad en konfigureret EKSTRA margen (min_delay_s), men aldrig under 30.
    delay_s = max(30, pw_cfg.get("min_delay_s", 30))
    max_pages = pw_cfg.get("max_pages_total", 40)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
    )

    raw_listings: list[dict] = []
    pages_fetched = 0
    for slug, subtype_hint in _CATEGORY_SLUGS.items():
        if pages_fetched >= max_pages:
            break
        try:
            page = 1
            while pages_fetched < max_pages:
                url = f"{BASE_URL}/vareliste/{slug}"
                params = {} if page == 1 else {"page": page}
                logger.info("Skave Nedbrydning: henter '%s' side %d", slug, page)
                resp = session.get(url, params=params, timeout=20)
                pages_fetched += 1
                if resp.status_code != 200:
                    logger.warning(
                        "Skave Nedbrydning: uventet status %d for '%s' side %d",
                        resp.status_code,
                        slug,
                        page,
                    )
                    break

                cards = _parse_cards(resp.text)
                if not cards:
                    break

                for card in cards:
                    if card["price"] is None:
                        continue
                    attributes = _parse_infos(card["infos_text"])
                    raw_listings.append(
                        {
                            "title": card["title"],
                            "description": card["description"],
                            "price_amount": card["price"],
                            "price_currency": "DKK",
                            "url": card["url"],
                            "origin_country_code": "DK",
                            "extra": {
                                "attributes": attributes,
                                "subtype_hint": subtype_hint,
                            },
                        }
                    )

                # 40 kort pr. side er sitets eget standard-sidestørrelse
                # (se modulets docstring -- ?limit= er disallowed).
                if len(cards) < 40:
                    break
                page += 1
                time.sleep(delay_s)
        except Exception:
            logger.exception(
                "Skave Nedbrydning: fejl under haandtering af '%s', springer over", slug
            )
            continue

    return raw_listings
