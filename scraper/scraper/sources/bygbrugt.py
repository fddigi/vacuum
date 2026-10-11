"""Bygbrugt.dk (Langå) -- den reneste datastruktur i en dedikeret Opus-
kildeevaluering af 16 sites (research/byggematerialer-kilder-2026-10-10.md,
afsnit 9): en ren HTML-TABEL pr. kategori med navngivne kolonner (Bredde,
Højde, Materiale, Farve, Lag glas), og EGNE kategori-URL'er for hver
brandklasse (BD30/BD60/BS60/dobbelte branddøre/brandporte/glasbranddøre) --
ingen anden kilde i hele undersøgelsen har brandklassen som STRUKTUR frem
for tekst i en titel.

WAF MED PROOF-OF-WORK, IKKE EN CAPTCHA: sitet bruger simply.com's Website
Application Firewall (samme som titan-genbrug.dk/demfranordlunde.dk).
Protokollen er reverse-engineeret fra selve klient-scriptet (hentet og læst
direkte 2026-10-10, ikke gættet):
  1. Et første GET giver HTTP 454 med siden "Checking your browser...". Dens
     <script> indeholder i klartekst `var T="<64 hex>",TS="<unix-ts>",D=16;`.
  2. Find et `nonce` (heltal fra 0) hvor sha256(f"{T}:{nonce}") har mindst D
     ledende nul-BITS (ikke hex-cifre -- se _leading_zero_bits()).
  3. POST `ts`, `nonce`, `token` (=T) som form-data til `/.sc-verify/`.
     Svar: `{"ok": true, "cookie": "<ts>|<hash>"}`.
  4. Sæt cookien `sc_clearance=<værdi>` for domænet -- herefter svarer alle
     almindelige GET-requests 200 i op til 24 timer (målt: cookien overlever
     flere på hinanden følgende kategori-hentninger uden at skulle gen-løses).
Målt løsningstid: 0,01--0,07 sekunder i ren Python (`hashlib`, INGEN browser,
INGEN Playwright) -- det er et bevidst omkostningsfyldt regnestykke for en
browser, men triviel at løse direkte.
Forbehold (målt): challenget er INTERMITTENT (nogle gange svarer sitet 200
uden challenge fra starten), og ved meget hyppig hentning kan sitet svare
HTTP 455 "Security Incident Detected" -- en hårdere rate-limit-tilstand, der
forsvinder af sig selv. Denne kilde retry-spammer ALDRIG på 455 (se
fetch()'s throttling).

INGEN PAGINERING AT HÅNDTERE: alle rækker i en kategori ligger i rå HTML på
én side (DataTables' egen paginering er klient-side kosmetik).

Kategorierne er fundet ved at læse forsidens kategori-navigation (ikke kun
den ene faste-karme-URL fra research-rapporten) -- se _CATEGORY_SLUGS.
"""

from __future__ import annotations

import hashlib
import logging
import random
import re
import time

import requests

logger = logging.getLogger("vacuum.bygbrugt")

BASE_URL = "https://www.bygbrugt.dk"
VERIFY_URL = BASE_URL + "/.sc-verify/"

_CHALLENGE_PATTERN = re.compile(r'var T="([0-9a-f]+)",TS="(\d+)",D=(\d+);')

# slug -> subtype_hint (se doere_normalize.classify_subtype()).
_CATEGORY_SLUGS = {
    "vinduer/facadevinduer/sidehaengte": "vindue",
    "vinduer/facadevinduer/tophaengte": "vindue",
    "vinduer/facadevinduer/faste-karme": "vindue",
    "vinduer/tagvinduer/nye": "vindue",
    "vinduer/tagvinduer/brugte": "vindue",
    "vinduer/tagvinduer/inddaekninger": "vindue",
    "vinduer/ovenlyskupler": "vindue",
    "doere/terrasse-doere": "terrassedoer",
    "doere/branddoere/bd30": "branddoer",
    "doere/branddoere/bd60": "branddoer",
    "doere/branddoere/bs60": "branddoer",
    "doere/branddoere/dobbelte-branddoere": "branddoer",
    "doere/branddoere/brandporte": "branddoer",
    "doere/branddoere/glasbranddoere": "branddoer",
    "doere/yderdoere": "doer_andet",
    "doere/indvendige-doere": "doer_andet",
    "doere/specialdoere": "doer_andet",
    "glas-og-glasdoere/glasdoere-uden-rammer": "doer_andet",
    # Brandglas er en komponent, ikke selve rammen -- samme princip som
    # jk-genbrugscenter.dk's 3 "Brandglas BD30"-produkter, som også ligger
    # under en vindues-kategori der der. "vindue" + fire-signal (brandordet
    # "brandglas" alene er nok, se classify_subtype()) giver "brandvindue".
    "glas-og-glasdoere/brandglas": "vindue",
}

# KOLONNE-LAYOUTET VARIERER PR. KATEGORI (målt live, 2026-10-10): vinduer har
# "Type" FØR Bredde/Højde, døre har INTET Type-felt der (Bred/Højde kommer
# direkte efter Antal), og brandglas-kategorien har hele FIRE ekstra felter
# (Type/Tykk./Vægt/BD). Et enkelt positions-fast regex kan derfor ikke dække
# alle layouts -- se _parse_rows() for den værdi-baserede tilgang i stedet
# (de to første plausible cm-mål EFTER Antal-cellen er altid bredde/højde,
# uanset hvor mange tekstfelter der kommer før/efter, verificeret mod både
# et vindues- og et dør-kort).
# MÅLT FUND (2026-10-10): "/doere/terrasse-doere" har ITU-BRUDT HTML på selve
# sitet -- 84 åbnende <tr class="product-entry">, men kun ÉT lukkende </tr>
# i hele siden (sammenlignet med 96/96 balanceret på faste-karme-siden). Et
# `(.*?)</tr>`-regex ville derfor sluge alle 83 rækker som én kæmpe blok.
# Rækker splittes i stedet på START-tagget alene (altid til stede), ALDRIG
# på et lukke-tag -- se _parse_rows().
_ROW_START_PATTERN = re.compile(r'<tr class="product-entry"[^>]*>')
_FIRST_LINK_PATTERN = re.compile(r'<td><a href="([^"]+)">([^<]*)</a>')
_PRICE_ORDER_PATTERN = re.compile(r'data-order="([\d.]+)"')
_CELL_PATTERN = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG_STRIP_PATTERN = re.compile(r"<[^>]+>")
# Et "plausibelt mål": 1-3 cifre, evt. med dansk decimal -- udelukker
# telefonnumre (har mellemrum) og priser med tusind-punktum som "1.500"
# IKKE udelukkes her (de optræder altid EFTER de to første mål-celler, så de
# generer ikke bredde/højde-udtrækket, se _parse_rows()).
_PLAUSIBLE_NUMBER_PATTERN = re.compile(r"^\d{1,3}(?:[.,]\d+)?$")


def _leading_zero_bits(hex_digest: str) -> int:
    """Tæller ledende nul-BITS, ikke hex-cifre -- porteret 1:1 fra sitets
    egen `lz()`-funktion i klient-scriptet (se modulets docstring).

    KRITISK FEJL FUNDET OG RETTET (2026-10-10/11): en tidligere version
    manglede `bits += 4` for hvert ledende nul-CIFRE og brugte kun `continue`
    uden akkumulering -- den returnerede derfor ALDRIG mere end 3 (den
    højeste partial-bit-værdi for et enkelt ikke-nul-cifre), uanset hvor
    mange ledende nuller der reelt var. Med D=16 ville `_solve_challenge()`
    i praksis ALDRIG terminere (kræver reelt et cifre-mønster der er
    astronomisk usandsynligt). Fanget ved at udregne forventede testværdier
    i hånden FØR testen blev skrevet -- ikke ved selve testkørslen, som
    ironisk nok ikke ville være fejlet med den gamle, forkerte funktion,
    fordi testen oprindelig (fejlagtigt) forventede samme forkerte adfærd."""
    bits = 0
    for ch in hex_digest:
        n = int(ch, 16)
        if n == 0:
            bits += 4
            continue
        if n < 2:
            bits += 3
        elif n < 4:
            bits += 2
        elif n < 8:
            bits += 1
        break
    return bits


def _solve_challenge(token: str, difficulty: int) -> int:
    """Finder det mindste nonce hvor sha256(f'{token}:{nonce}') har mindst
    `difficulty` ledende nul-bits. Målt 0,01-0,07s i produktion -- ingen
    øvre grænse nødvendig her."""
    nonce = 0
    while True:
        digest = hashlib.sha256(f"{token}:{nonce}".encode()).hexdigest()
        if _leading_zero_bits(digest) >= difficulty:
            return nonce
        nonce += 1


def _ensure_cleared(session: requests.Session, url: str) -> requests.Response:
    """Henter `url`; løser WAF-challenget og gen-henter hvis sitet svarer
    454. 455 ("Security Incident Detected") er en hårdere rate-limit --
    denne funktion giver IKKE op til den selv (se fetch()'s throttling i
    stedet, som er det der reelt forebygger 455)."""
    resp = session.get(url, timeout=20)
    if resp.status_code != 454:
        return resp

    m = _CHALLENGE_PATTERN.search(resp.text)
    if not m:
        logger.warning("Bygbrugt: 454 uden genkendeligt challenge-format for %s", url)
        return resp
    token, ts, difficulty = m.group(1), m.group(2), int(m.group(3))
    nonce = _solve_challenge(token, difficulty)

    verify = session.post(
        VERIFY_URL,
        data={"ts": ts, "nonce": str(nonce), "token": token},
        timeout=20,
    )
    try:
        payload = verify.json()
    except ValueError:
        logger.warning("Bygbrugt: uventet svar fra /.sc-verify/ for %s", url)
        return resp
    if not payload.get("ok"):
        logger.warning("Bygbrugt: WAF-verifikation afvist for %s: %s", url, payload)
        return resp

    # Domænet sættes UDEN "www." (se klient-scriptets egen
    # `domain=bygbrugt.dk`) -- cookie-matching dækker så begge.
    session.cookies.set("sc_clearance", payload["cookie"], domain="bygbrugt.dk")
    return session.get(url, timeout=20)


def _danish_decimal_to_float(text: str) -> float | None:
    cleaned = (text or "").replace(".", "").replace(",", ".").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_rows(html: str) -> list[dict]:
    """Se _ROW_START_PATTERN's kommentar for hvorfor rækker splittes på
    START-tagget (aldrig et `</tr>`-regex): bredde/højde findes som de to
    FØRSTE plausible tal-celler efter de tre faste indledende celler
    (billede/varenr/antal, altid i denne rækkefølge uanset kategori --
    Antal-cellen er selv enten et bart tal eller et par nestede venstre/
    højre-hængt-divs, begge tilfælde springes over ved blot at tælle
    celle-position, ikke ved at parse dens indhold)."""
    starts = [m.start() for m in _ROW_START_PATTERN.finditer(html)]
    results = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(html)
        block = html[start:end]
        link_m = _FIRST_LINK_PATTERN.search(block)
        if not link_m:
            continue
        href, varenr = link_m.group(1), link_m.group(2).strip()
        url = href if href.startswith("http") else BASE_URL + href

        price_m = _PRICE_ORDER_PATTERN.search(block)
        price = _danish_decimal_to_float(price_m.group(1)) if price_m else None

        cells = [_TAG_STRIP_PATTERN.sub("", c).strip() for c in _CELL_PATTERN.findall(block)]
        # cells[0]=billede, cells[1]=varenr (allerede hentet), cells[2]=antal.
        remaining = cells[3:]
        numeric = [c for c in remaining if _PLAUSIBLE_NUMBER_PATTERN.match(c)]
        width_cm = _danish_decimal_to_float(numeric[0]) if len(numeric) >= 1 else None
        height_cm = _danish_decimal_to_float(numeric[1]) if len(numeric) >= 2 else None
        # Beskrivelsesfelter: alle resterende tekst-celler undtagen pris
        # (allerede hentet separat), telefonnummer (indeholder mellemrum
        # mellem cifre) og "Mere"-handlingslinket.
        text_cells = [
            c
            for c in remaining
            if c
            and c != "Mere"
            and not _PLAUSIBLE_NUMBER_PATTERN.match(c)
            and not re.match(r"^[\d\s]+$", c)
        ]

        results.append(
            {
                "varenr": varenr,
                "width_cm": width_cm,
                "height_cm": height_cm,
                "description_parts": text_cells,
                "price": price,
                "url": url,
            }
        )
    return results


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    pw_cfg = config.get("playwright", {})
    min_delay = pw_cfg.get("min_delay_s", 2)
    max_delay = pw_cfg.get("max_delay_s", 5)

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
    for slug, subtype_hint in _CATEGORY_SLUGS.items():
        url = f"{BASE_URL}/{slug}"
        try:
            logger.info("Bygbrugt: henter %s", slug)
            resp = _ensure_cleared(session, url)
            if resp.status_code == 455:
                logger.warning(
                    "Bygbrugt: 455 (Security Incident Detected) for %s -- springer "
                    "resten af denne kørsel over for at undgå at optrappe",
                    slug,
                )
                break
            if resp.status_code != 200:
                logger.warning(
                    "Bygbrugt: uventet status %d for %s, springer kategorien over",
                    resp.status_code,
                    slug,
                )
                continue

            for row in _parse_rows(resp.text):
                if row["price"] is None or row["price"] <= 0:
                    continue
                attributes = {}
                if row["width_cm"] is not None:
                    attributes["width_cm"] = row["width_cm"]
                if row["height_cm"] is not None:
                    attributes["height_cm"] = row["height_cm"]

                title = row["varenr"] or "Uden titel"
                if slug == "glas-og-glasdoere/brandglas":
                    # MÅLT 2026-10-10: denne kategoris egne "Type"/"BD"-
                    # kolonner bruger sitets interne forkortelse "E30"/"E60"
                    # (ikke "EI30"/"EI60"), som hverken doere_normalize.py's
                    # _FIRE_CLASS_PATTERN eller _BRAND_WORD matcher. Da
                    # KATEGORIEN selv er beviset for at varen er brandglas
                    # (uanset varenrens egen tekst), forstærkes titlen
                    # eksplicit, så den almindelige brandord-detektion
                    # (classify_subtype()) fanger den uden en skrøbelig
                    # site-specifik "E"-kode-regel i den delte, generiske kode.
                    title = f"Brandglas {title}"

                raw_listings.append(
                    {
                        "title": title,
                        "description": " ".join(row["description_parts"]),
                        "price_amount": row["price"],
                        "price_currency": "DKK",
                        "url": row["url"],
                        "origin_country_code": "DK",
                        "extra": {
                            "attributes": attributes,
                            "subtype_hint": subtype_hint,
                        },
                    }
                )

            time.sleep(random.uniform(min_delay, max_delay))
        except Exception:
            logger.exception("Bygbrugt: fejl under haandtering af '%s', springer over", slug)
            continue

    return raw_listings
