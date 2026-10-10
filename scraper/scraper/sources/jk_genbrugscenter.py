"""JK-Genbrugscenter.dk (Odense) -- genbrugs døre/vinduer, herunder en
dedikeret Branddøre-kategori. Ren `requests`-kilde: sitet eksponerer sit eget
WooCommerce Store API UAUTENTIFICERET og offentligt (ingen nøgle, ingen
login, verificeret live 2026-10-10):

    GET /wp-json/wc/store/v1/products?per_page=100&page=N

Ingen bot-beskyttelse, intet JS nødvendigt -- almindelig `requests` er nok,
samme kategori-2-kilde som genbyg.py.

HELE KATALOGET HENTES, IKKE ET SØGEORD-LOOP (samme princip som
jyskauktion.py for katalog-browse-kilder, se dens docstring): siden har
INGEN fritekstsøgning der giver mening at loope over -- i stedet filtreres
der på WooCommerce'ens egne, stabile kategori-ID'er (se RELEVANT_CATEGORY_IDS
nedenfor), fundet ved at hente hele kategori-træet først
(`/products/categories`) og manuelt verificere hvilke IDs der reelt er
døre/vinduer (1453 varer i alt på sitet, heraf kun ~1180 relevante -- resten
er tømmer, radiatorer, tagsten, trapper osv., se den fulde opdeling i
research/byggematerialer-kilder-2026-10-10.md).

STRUKTURERET DATA, MEN IKKE I ET DEDIKERET FELT: WooCommerce's eget
`dimensions`-felt (`length`/`width`/`height`) bruges IKKE af denne sælger --
det er altid tomt (verificeret på 1453/1453 varer). Mål står i stedet som
ensartet formateret tekst i `short_description`
("<p><strong>Bredde 95</strong></p><p><strong>Højde 239</strong></p>"),
MÅLT 80,3% dækning på tværs af HELE kataloget (97% inden for Branddøre- og
Terrassedør-kategorierne specifikt) -- stadig markant mere pålideligt end
DBA's fritekst-titel, fordi feltet selv er navngivet og konsekvent formateret
pr. vare, ikke en fritekst-sætning scraperen selv skal gætte struktur i.

KATEGORI-BASERET SUBTYPE-HINT (se doere_normalize.classify_subtype()):
sitets EGEN kategori-tildeling er mere pålidelig end en tekstsøgning for
terrassedør-genkendelse -- MÅLT fund: 2 af 15 stikprøvede "Terrassedør"-
kategoriserede varer hed rent faktisk "Hæveskydedør"/"Skydedør" i selve
titlen, ikke "terrassedør". Et tekstbaseret filter ville have misset dem.
"""

from __future__ import annotations

import html
import logging
import random
import re
import time

import requests

logger = logging.getLogger("vacuum.jk_genbrugscenter")

BASE_URL = "https://jk-genbrugscenter.dk"
PRODUCTS_URL = BASE_URL + "/wp-json/wc/store/v1/products"

# MÅLT 2026-10-10 (se modulets docstring + research/byggematerialer-kilder-
# 2026-10-10.md's afsnit 1): kategori-ID'er er stabile WooCommerce-term-ID'er,
# ikke noget der roterer som fx jyskauktion.dk's katalog-ID'er.
_BRANDDOOR_CATEGORY_ID = 210
_TERRASSEDOOR_CATEGORY_ID = 208
_ACCESSORY_CATEGORY_ID = 218  # "Dør Tilbehør lås/Hængsler mm" -- springes over
_VINDUE_CATEGORY_IDS = {
    205,  # Nye og brugte vinduer (parent)
    483,  # Sidehængt vindue
    334,  # Tophængte vinduer
    339,  # Fastkarmsvindue
    340,  # Vinduesparti
    338,  # Plast vinduer
    980,  # Badeværelsesvindue
    336,  # Dannebrogs vinduer
    539,  # Dreje kip vinduer
    337,  # Antik vindue
    335,  # Bondehusvinduer
    216,  # Runde og special-vinduer
    463,  # Ovenlysvindue
    464,  # Støbejernsvindue
}
_DOOR_OTHER_CATEGORY_IDS = {
    207,  # Nye og brugte døre (parent)
    213,  # Fyldningsdøre uden karm
    219,  # Indvendigedøre
    209,  # Facadedør
    214,  # Fyldningsdøre med karm
    658,  # Sikringsdør
    885,  # Porte
}
_RELEVANT_CATEGORY_IDS = (
    _VINDUE_CATEGORY_IDS
    | _DOOR_OTHER_CATEGORY_IDS
    | {_BRANDDOOR_CATEGORY_ID, _TERRASSEDOOR_CATEGORY_ID}
)

# MÅLT 2026-10-10: separatoren mellem "Bredde"/"Højde" og selve tallet er
# IKKE ensartet -- det er manuel tekst-indtastning af forskelligt personale.
# Fundet på tværs af hele kataloget: "Bredde 108", "Bredde. 60", "Bredde: 60",
# "Bredde.: 60", "Bredde..: 60", "Bredde \xa0 60" (hårdt mellemrum), "Bredde .
# 60". Et stramt `\s*` (kun whitespace) ramte derfor kun 49/73 (67%) af
# Branddøre-kategorien.
#
# ANDET MÅLT FUND, VIGTIGERE: en første rettelse brugte `[^\d]*?` (lazy) FØR
# tal-gruppen `[\d.,]+` -- men `[\d.,]+` optager OGSÅ punktum/komma, så den
# lazy separator-gruppe kunne under-matche og lade et enkelt "." fra fx
# "Bredde. 59" blive fanget SOM selve tallet (group(1) = "."), hvilket gav
# en ValueError ved float() og dermed et STILLE farvet 0-resultat -- regexet
# "matchede" (dims-dækning SÅ korrekt ud ved et overfladisk regex-check),
# men selve parsingen fejlede for 23 af 73 Branddøre. Rettelsen: tal-gruppen
# skal starte med et cifre (`\d[\d.,]*`), og separatoren er `\D*?` (alt
# ikke-cifret) -- så en separator der tilfældigvis ender på "." aldrig kan
# blive fejltolket som tallets begyndelse. Efter denne rettelse: 72/73 (99%)
# Branddøre, 91/91 (100%) Terrassedør, 691/716 (97%) vindue-kategorier.
_DIM_PATTERN = re.compile(r"Bredde\D*?(\d[\d.,]*).*?H[øo]jde\D*?(\d[\d.,]*)", re.I | re.S)
_TAG_PATTERN = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return html.unescape(_TAG_PATTERN.sub(" ", text or "")).strip()


def _clean_title(text: str) -> str:
    """`name` fra Store API'et er IKKE HTML (ingen tags), men WordPress
    leverer den stadig HTML-entity-encodet -- MÅLT fund: "Ståldør &#8211;
    Novoferm" i stedet for "Ståldør – Novoferm", "94&#215;160 cm" i stedet
    for "94×160 cm". Uden afkodning ville både dashboardet og tekstudtræk
    (fx extract_fire_rating) se de rå entity-koder i stedet for teksten."""
    return html.unescape(text or "").strip()


def _parse_dimensions(short_description: str) -> dict:
    m = _DIM_PATTERN.search(short_description or "")
    if not m:
        return {}
    try:
        width = float(m.group(1).replace(",", "."))
        height = float(m.group(2).replace(",", "."))
    except ValueError:
        return {}
    return {"width_cm": width, "height_cm": height}


def _subtype_hint_for(category_ids: set[int]) -> str | None:
    """Se doere_normalize.classify_subtype()'s docstring for hvorfor
    branddør/terrassedør-ID'et tjekkes FØR det generiske vindue/dør-tjek --
    en vare kan ligge i flere kategorier samtidig (fx både "Fastkarmsvindue"
    og "Vinduesparti"), men branddør/terrassedør er den mest specifikke."""
    if _BRANDDOOR_CATEGORY_ID in category_ids:
        return "branddoer"
    if _TERRASSEDOOR_CATEGORY_ID in category_ids:
        return "terrassedoer"
    if category_ids & _VINDUE_CATEGORY_IDS:
        return "vindue"
    if category_ids & _DOOR_OTHER_CATEGORY_IDS:
        return "doer_andet"
    return None


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    pw_cfg = config.get("playwright", {})
    min_delay = pw_cfg.get("min_delay_s", 1)
    max_delay = pw_cfg.get("max_delay_s", 2)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; vacuum-scraper/1.0)"})

    raw_listings: list[dict] = []
    page = 1
    try:
        while True:
            logger.info("JK-Genbrugscenter: henter side %d", page)
            resp = session.get(
                PRODUCTS_URL, params={"per_page": 100, "page": page}, timeout=20
            )
            if resp.status_code != 200:
                logger.warning(
                    "JK-Genbrugscenter: uventet status %d på side %d, stopper",
                    resp.status_code,
                    page,
                )
                break
            batch = resp.json()
            if not batch:
                break

            for product in batch:
                category_ids = {c["id"] for c in product.get("categories", [])}
                if _ACCESSORY_CATEGORY_ID in category_ids:
                    continue
                subtype_hint = _subtype_hint_for(category_ids)
                if subtype_hint is None:
                    continue  # uden for RELEVANT_CATEGORY_IDS -- tømmer/radiator/tagsten osv.

                price_minor = product.get("prices", {}).get("price")
                if price_minor is None:
                    continue
                try:
                    amount = float(price_minor) / 100.0
                except (TypeError, ValueError):
                    continue
                if amount <= 0:
                    continue

                images = product.get("images") or []
                attributes = _parse_dimensions(product.get("short_description", ""))

                raw_listings.append(
                    {
                        "title": _clean_title(product.get("name", "")),
                        "description": _strip_html(product.get("description", "")),
                        "price_amount": amount,
                        "price_currency": "DKK",
                        "url": product.get("permalink", ""),
                        "origin_country_code": "DK",
                        "extra": {
                            "image_url": images[0]["src"] if images else None,
                            "attributes": attributes,
                            "subtype_hint": subtype_hint,
                            "sku": product.get("sku"),
                        },
                    }
                )

            if len(batch) < 100:
                break
            page += 1
            time.sleep(random.uniform(min_delay, max_delay))
    except Exception:
        logger.exception(
            "JK-Genbrugscenter: kilden fejlede helt, springer kilden over for denne koersel"
        )
        return raw_listings

    return raw_listings
