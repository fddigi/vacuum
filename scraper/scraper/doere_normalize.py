"""Normalisering for kategorien "døre" (SHV-sourcing, se categories.py).

Samme kontrakt som scraper.normalize.normalize_listing(), men med dørens
egne attributter (bredde/højde/tykkelse/brandklasse) i stedet for
støvsugerens (støvklasse/asbestgodkendelse).

TO DATAKILDE-TYPER, samme output-form: nogle kilder (genbyg.dk) leverer
STRUKTUREREDE mål direkte pr. kort (se sources/genbyg.py -- "Bredde: 92,70
cm" som et eget felt, ikke fritekst), andre (dba.dk) har kun en fritekst-
titel ("82x204 cm" et sted i sætningen). Begge ender i samme
`listing["attributes"]`-form (width_cm/height_cm/thickness_cm/fire_rating),
så classify.py aldrig behøver vide hvilken kilde-type en annonce kom fra.
Prioritet: struktureret kilde-data (extra["attributes"]) vinder ALTID over
tekstudtræk, når begge findes -- en kildes egen strukturerede felt er pr.
definition mere pålideligt end et regex-gæt på samme kilde-tekst.

FRITEKST-UDTRÆKKET NEDENFOR (extract_dimensions_from_text/extract_fire_rating)
ER PORTERET FRA EN DEDIKERET OPUS-UNDERSØGELSE (2026-10-04) af 1.959 rigtige
dba.dk dør-/vinduesannoncer -- IKKE et førstegangs-gæt. Den oprindelige,
naive version af dette modul (`\\d{2,3}\\s*[x×]\\s*\\d{2,3}`) blev målt bagefter
mod samme korpus: 168 hits, men 41 af dem (24%) var FAKTISK FORKERTE --
20 med bredde/højde ombyttet (sælgere skriver ofte højde FØRST: "204 x 82
cm"), 14 med decimaler afskåret ("83x201,5" -> 83x201, mister netop de
almindelige danske dørbredder 72,5/82,5/92,5 cm), 5 med mm fejlagtigt læst
som cm. Det nye udtræk herunder måler 426 hits (2,5x flere) med 99,8%
præcision på samme korpus -- se README's SHV-afsnit for den fulde rapport.
"""

from __future__ import annotations

import re

NUM = r"\d{1,4}(?:[.,]\d{1,2})?"
UNIT = r"(?:cm|mm)"
# Et tal kan stå som et INTERVAL i rigtige annoncer ("118-119cm",
# "105/106 x 203", "89 x 209/210 cm") -- vi tager altid den FØRSTE værdi
# (sælgerens primære mål) og ignorerer resten af intervallet.
NUMR = NUM + r"(?:\s*[/-]\s*" + NUM + r")?"

# ---------------------------------------------------------------------------
# STØJ-SPAN: tal der aldrig er et dørmål. Fjernes FØR alle grene.
#
# BEMÆRK det bevidst FRAVÆRENDE: et bart årstal-mønster (\b(?:19|20)\d{2}\b).
# Det var med i et tidligere udkast og var den enkeltstørste fejlkilde: en
# dørhøjde i MILLIMETER er systematisk 1940-2143, dvs. den ligger ovenpå
# årstalsintervallet. Målt konsekvens af det bare årstalsfilter: 11 ægte mål
# tabt, bl.a. "Indvendig dør 2040 x 825 mm", "Fyldningsdør, fyrretræ, b: 825
# h: 2036", "Swedoor glasdør 825 x 1940". Et årstal kræver derfor nu et
# eksplicit ANKERORD foran ("fra 1904", "årg. 2014", "år 1900").
_NOISE_SPANS = re.compile(
    "|".join(
        [
            r"\b(?:kr|pris(?:en)?|bud|stk|styk|st\.|[åa]rg\.?|anno|ral|punkt|pers|"
            r"liter|ml|fods|hk|zone[r]?|lags?|fags?|serie|nr\.?|mk|u)\b\s*\.?\s*" + NUM,
            NUM + r"\s*(?:-\s*)?(?:kr\b|kroner|stk\b|styk\b|fags?\b|lags?\b|punkts?\b|"
            r"%|pers\b|liter\b|ml\b|fods\b|hk\b|watt\b|w\b|v\b|zoner?\b|"
            r"spejl\b|ruder\b|rude\b|glas\b|felter\b|paneler\b|etager\b|knager\b|[åa]r\b)",
            NUM + r"\s*,-",  # "275,-" (pris)
            r"\b(?:bd|ei|ew|el|bs|fd|rb|rbg|ry|db|sp|gw|mk|dc|az|hk|vk|ggl|gv)\s*-?\s*\d{1,4}\b",
            r"\b[ef]\s*-\s*\d{2,3}\b",
            r"\b\d{2,3}\s*db\b",
            r"\b(?:fra|[åa]r|[åa]rg\.?|anno|siden|ca\.?)\s+(?:1[5-9]|20)\d{2}\b",
            r"\b(?:1[5-9]|20)\d{2}\s*(?:'|’)?er",  # "1950'erne", "1960'er"
            r"\b[øo]\s*\d{1,3}\b",  # "ø16 dørgreb"
        ]
    ),
    re.I,
)

# GREN 1: NAVNGIVNE MÅL -- label FØR tallet ELLER rolleord EFTER tallet. De to
# er samlet i én opsamling, fordi rigtige titler blander dem: "Højde 203 cm
# 78 cm bred" (prefix + suffix i samme titel), "mål 78 cm brede by højde
# 212cm." ("by" i stedet for "x"!).
_LABEL_PREFIX = re.compile(
    r"(?P<lab>bredde|br\.|h[øo]jde|dybde|l[æa]ngde|\bb|\bh|\bd|\bl)\s*[:=.]?\s*"
    r"(?P<v>" + NUMR + r")\s*(?P<u>" + UNIT + r")?",
    re.I,
)
_ROLE_SUFFIX = re.compile(
    r"(?P<v>" + NUMR + r")\s*(?P<u>" + UNIT + r")?\s*"
    r"(?P<role>h[øo]je?\b|h[øo]jde\b|brede?\b|bredde\b|dybe?\b|dybde\b)",
    re.I,
)

# GREN 2: BART TALPAR. Lookaheads er bevidst `(?![.,]?\d)` og IKKE
# `(?![\d,.])`: en afsluttende sætningsprik ("72,5 x 204. stk pris!",
# "600x600x600 mm,") fik ellers hele matchet til at fejle.
_BARE_PAIR = re.compile(
    r"(?<![\d,.])(?P<v1>" + NUMR + r")\s*[x×*]\s*(?P<v2>" + NUMR + r")"
    r"(?:\s*[x×*]\s*(?P<v3>" + NUMR + r"))?"
    r"\s*(?P<u>" + UNIT + r")?(?![.,]?\d)",
    re.I,
)

# GREN 3: DANSK MODULMÅL i decimeter ("9x21", "8x21", "M9*21", "10x21"). 9x21
# CM findes ikke som dør eller vindue, så der er ingen tvetydighed.
_MODULE_PAIR = re.compile(
    r"(?<![\d,.])\b[mM]?(?P<w>\d|1[0-9])\s*[x×*]\s*(?P<h>1\d|2\d)\b(?![\d,.])"
)

_SINGLE_UNIT = re.compile(r"(?<![\d,.])(?P<v>" + NUM + r")\s*(?P<u>" + UNIT + r")\b", re.I)

# Tilbehør/ikke-emne: et mål i en sådan titel er skinnelængde, karmbredde,
# grebsdiameter eller sprossebredde -- aldrig dørbladets mål.
_ACCESSORY_HEAD = re.compile(
    r"\b(skinnes[æa]t|skinne|liste|gummiliste|t[æa]tningsliste|d[øo]rgreb|greb|"
    r"h[åa]ndtag|h[æa]ngsel|h[æa]ngsler|beslag|l[åa]s\w*|skudrigel|magnetl[åa]s|"
    r"karms[æa]t|karm|sprosse\w*|d[øo]rtrin|bundstykke|d[øo]rpumpe|insektnet|"
    r"knager[æa]kke|skostativ|spejl|sensor|rel[æa]|n[øo]gleskilt|roset|husnummer|"
    r"glasliste|oph[æa]ng|bj[æa]lke|plissegardin|gardin|net\b|monteringss[æa]t)\b",
    re.I,
)

_MIN_CM, _MAX_CM = 20.0, 400.0
_DOOR_H_MIN, _DOOR_H_MAX = 150.0, 285.0

# Dansk sammensætning: "glasdør", "yderdør", "branddør" har INGEN ordgrænse
# foran "dør" -- derfor intet venstre-\b (samme rettelse som normalize.py's
# säck/beutel/adapter).
_DOOR_WORD = re.compile(r"d[øo]r(?:e|en|a)?\b|\bport\b", re.I)

# ---------------------------------------------------------------------------
# TILBEHØR/UDLEJNING. RETTET 2026-10-04 (samme lektie som normalize.py's R11
# -- se dennes docstring): den oprindelige ACCESSORY_TITLE_PATTERN afviste
# håndværks-ord UANSET kontekst og tabte derved 23 af 40 ramte titler, som
# reelt var HELE døre, hvor beslaget bare er en del af salget ("med
# dørpumpe", "med håndtag inkl. karm", "m. hængsler"). Et tilbehørsord
# diskvalificerer nu KUN når det er titlens EGET hovedord (ingen "dør/vindue/
# karm"-reference i samme titel) -- ikke når det optræder i en "med/inkl./m./
# uden <beslag>"-konstruktion sammen med en reel dør/vindue-reference.
ACCESSORY_OR_RENTAL_PATTERN = re.compile(
    r"\b(udlejning|til\s*leje|søges|k[øo]bes)\b",
    re.I,
)
# "karmsæt" tilføjet 2026-10-05 (P11, Opus-review): "Swedoor karmsæt tung
# 128 mm 8x21" blev vist som en hel dør (_MODULE_PAIR læste "8x21" som
# 80x210cm), men er et løst karmsæt. Bevidst KUN dette ord, ikke hele
# _ACCESSORY_HEAD-ordforrådet ovenfor -- målt konsekvens af den bredere
# liste ville være 30 fejlafviste hele døre for 1 korrekt fangst (samme R11-
# lektie: karm/skinne/lås nævnes tit i "med karm"-salg af en hel dør).
_ACCESSORY_WORD = re.compile(
    r"\b(d[øo]rgreb[\w]*|h[åa]ndtag|h[æa]ngsel|h[æa]ngsler|d[øo]rpumpe[r]?|d[øo]rstopper[e]?|"
    r"karms[æa]t)\b",
    re.I,
)
_INCLUDED_HARDWARE_CONTEXT = re.compile(r"\b(med|inkl\.?|uden)\b|\bm\.", re.I)


def is_accessory_or_rental(text: str) -> bool:
    return bool(ACCESSORY_OR_RENTAL_PATTERN.search(text or ""))


def is_accessory_title(title: str) -> bool:
    title = title or ""
    if not _ACCESSORY_WORD.search(title):
        return False
    # Beslaget er inkluderet i en HEL dørs salg, ikke selve emnet -- se
    # modulets kommentar ovenfor for det konkrete fund (23/40 falske
    # positiver). "glasdør"/"skydedør" har ingen venstre-\b på samme måde
    # som _DOOR_WORD ovenfor.
    if _DOOR_WORD.search(title) and _INCLUDED_HARDWARE_CONTEXT.search(title):
        return False
    return True


def _num(s: str) -> float:
    """Første værdi i et evt. interval ("105/106" -> 105, "118-119" -> 118)."""
    first = re.split(r"\s*[/-]\s*", s.strip())[0]
    return float(first.replace(",", "."))


def _to_cm(values: list[float], unit: str | None) -> list[float]:
    """mm -> cm, PR. VÆRDI. To målte grunde til at gøre det pr. værdi og ikke
    pr. match: (1) STØRRELSEN overtrumfer en eksplicit enhed, fordi sælgere
    skriver den forkerte ("825x1940x49cm" er mm, en 825 cm bred dør findes
    ikke); (2) sælgere BLANDER enheder inden for ét mål ("b: 825 h: 204" --
    bredde i mm, højde i cm). En fælles skalering ville her give en dør på
    20 cm."""
    out = []
    for v in values:
        if v >= 400:
            out.append(v / 10.0)
        elif unit and unit.lower() == "mm":
            out.append(v / 10.0)
        else:
            out.append(v)
    return out


def _finalize(cm: list[float], *, is_door: bool) -> dict:
    if len(cm) >= 3:
        # Tredje tal er tykkelsen ("92,5 x 214 x 4 cm") -- fjernes PÅ VÆRDI,
        # ikke på position, fordi sælgerne skriver den både først, i midten
        # og sidst.
        cm = sorted([v for v in cm if v >= _MIN_CM], reverse=True)[:2]
    if len(cm) != 2:
        return {}
    if any(v < _MIN_CM or v > _MAX_CM for v in cm):
        return {}
    if is_door:
        # Dørhøjden er det tal der ligger i dørhøjde-intervallet. Hvis BEGGE
        # gør (dobbeltdør "260 x 212"), vinder det ANDET tal: dansk
        # annoncekonvention er bredde-først (målt, se modulets docstring).
        if _DOOR_H_MIN <= cm[1] <= _DOOR_H_MAX:
            return {"width_cm": cm[0], "height_cm": cm[1]}
        if _DOOR_H_MIN <= cm[0] <= _DOOR_H_MAX:
            return {"width_cm": cm[1], "height_cm": cm[0]}
        return {}
    return {"width_cm": min(cm), "height_cm": max(cm)}


def _role_key(word: str) -> str:
    """Første bogstav afgør aksen -- b(redde)/h(øjde)/d(ybde)/l(ængde).
    Bevidst på FØRSTE BOGSTAV og ikke på hele ordet, fordi begge skrivemåder
    findes side om side i data ("B:91, H:212" vs "højde 216,5, bredde 88")."""
    return word.strip().lower()[0]


def extract_dimensions_from_text(text: str) -> dict:
    """Fallback-udtræk når kilden ikke selv leverer strukturerede mål -- se
    modulets docstring for den målte begrundelse bag hver gren. Returnerer
    {} hvis intet mål-mønster findes."""
    t = text or ""
    is_door = bool(_DOOR_WORD.search(t))
    clean = _NOISE_SPANS.sub(" ", t)

    # ---- GREN 1: navngivne mål (prefix-label og/eller suffix-rolleord)
    got: dict[str, float] = {}
    explicit: set[str] = set()  # label skrevet som helt ord, ikke bart bogstav
    unit = None
    for m in _LABEL_PREFIX.finditer(clean):
        lab = m.group("lab").strip()
        key = _role_key(lab)
        if key not in got:
            got[key] = _num(m.group("v"))
            if len(lab) > 2:
                explicit.add(key)
        unit = unit or m.group("u")
    for m in _ROLE_SUFFIX.finditer(clean):
        key = _role_key(m.group("role"))
        if key not in got:
            got[key] = _num(m.group("v"))
            explicit.add(key)
        unit = unit or m.group("u")
    if "b" in got and ("h" in got or "l" in got):
        pair = _to_cm([got["b"], got.get("h", got.get("l"))], unit)
        if all(_MIN_CM <= v <= _MAX_CM for v in pair):
            return {"width_cm": pair[0], "height_cm": pair[1]}

    # ---- GREN 3 FØR GREN 2: modulmål ville ellers læses som 9x21 cm
    mod = _MODULE_PAIR.search(clean)
    if mod:
        w, h = float(mod.group("w")) * 10, float(mod.group("h")) * 10
        if 50 <= w <= 200 and _DOOR_H_MIN <= h <= _DOOR_H_MAX:
            return {"width_cm": w, "height_cm": h}

    # ---- GREN 2: bart talpar
    for bm in _BARE_PAIR.finditer(clean):
        vals = [_num(bm.group("v1")), _num(bm.group("v2"))]
        if bm.group("v3"):
            vals.append(_num(bm.group("v3")))
        out = _finalize(_to_cm(vals, bm.group("u")), is_door=is_door)
        if out:
            return out

    # ---- GREN 4: ét mål. Kun på selve emnet, aldrig på tilbehør.
    if not _ACCESSORY_HEAD.search(t):
        for key in ("h", "b"):
            if key in explicit:
                v = _to_cm([got[key]], unit)[0]
                if _MIN_CM <= v <= _MAX_CM:
                    field = "height_cm" if key == "h" else "width_cm"
                    return {field: v}
        sm = _SINGLE_UNIT.search(clean)
        if sm and is_door:
            v = _to_cm([_num(sm.group("v"))], sm.group("u"))[0]
            if _DOOR_H_MIN <= v <= _DOOR_H_MAX:
                return {"height_cm": v}
    return {}


# ---------------------------------------------------------------------------
# BRANDKLASSE. To FORSKELLIGE systemer, og begge står på DØRE i det
# undersøgte korpus: BD30/BD60 (gammel dansk betegnelse, klart mest brugt),
# EI30/EI60/EI120 (EN 13501-2, gældende europæisk -- staves ofte "EL30" pga.
# stort I/lille l-forveksling), BS60 (gammel dansk "brandsikker"), F-30
# (ældre F-klasse), FD30 (engelsk "fire door").
#
# RETTET 2026-10-04: en tidligere version af denne kommentar hævdede "BD for
# døre, EI for ruder/vinduer" -- det holder IKKE. Research fandt EI på
# ståldøre ("EI60 stål branddør mål 139 x 260 cm") og BD på glas ("Brandglas
# BD30"). Systemvalget følger SÆLGERENS ordvalg (ofte årgang), ikke
# bygningsdelens type -- derfor ingen forsøgt dør/glas-opdeling her.
_FIRE_CLASS_PATTERN = re.compile(r"\b(bd|ei|el|bs|fd|ew|f)\s*-?\s*(30|35|45|60|90|120)\b", re.I)
# "Brandglas 60 mål 121 x 209 cm" / "Brandglas 30": klassetallet alene, med
# brand-ordet som anker. Uden ankeret ville ethvert løst "60" blive en
# brandklasse.
_FIRE_BARE_PATTERN = re.compile(
    r"\bbrand(?:glas|rude|d[øo]re?|parti\w*|vindue\w*)\s*(30|60|90|120)\b", re.I
)

# P3 (Opus-review, 2026-10-05): _FIRE_CLASS_PATTERN alene krævede intet dør-/
# vindueskontekst og gav 3 MÅLTE falske positiver -- "BD"/"BS" læst af helt
# andre produkters eget typenummer: "Blu-ray afspiller, Panasonic, BMP-BD30"
# (BD = Blu-ray Disc), "Wacker BS60-4 Jordloppe", "Jordloppe Wacker
# BS60-2i" (BS60 = en jordstamperens eget modelnummer, intet med
# "brandsikker" at gøre). Et klassetal kræver derfor nu ET af disse ord et
# sted i titlen. _FIRE_BARE_PATTERN er allerede selv-ankret ("brand"+glas/
# dør/vindue/parti) og har intet ekstra kontekstkrav nødvendigt.
_FIRE_CONTEXT_WORD = re.compile(
    r"d[øo]r(?:e|en|a)?\b|\bport\b|vindue\w*|glas\w*|parti\w*|\blem\b|karm\w*", re.I
)


def extract_fire_rating(text: str) -> str | None:
    t = text or ""
    has_context = bool(_FIRE_CONTEXT_WORD.search(t))
    hits = []
    if has_context:
        for m in _FIRE_CLASS_PATTERN.finditer(t):
            sys_ = m.group(1).upper()
            sys_ = "EI" if sys_ == "EL" else sys_
            hits.append(f"{sys_}{m.group(2)}")
    for m in _FIRE_BARE_PATTERN.finditer(t):
        hits.append(f"BD{m.group(1)}")  # dansk kontekst -> BD-systemet som default
    if not hits:
        return None
    return sorted(set(hits))[0]


# ---------------------------------------------------------------------------
# SUBTYPE (2026-10-10): brugerens eget opdrag -- "gøre klar til at inddele i
# brandvinduer, branddøre, terrassedør og vinduer" i dashboardet. Lagres som
# attributes["subtype"] (samme generiske attributes_json-kolonne som mål/
# brandklasse, ingen skemaændring nødvendig).
#
# `category_hint` (valgfri, sat af en kildes egen fetch() via
# extra["subtype_hint"]) vinder ALTID over tekstgæt, når den findes -- samme
# princip som strukturerede mål vinder over regex. Konkret fund bag dette
# (jk-genbrugscenter.dk, 2026-10-10): 2 af 15 stikprøvede "Terrassedør"-
# kategoriserede varer hed rent faktisk "Hæveskydedør"/"Skydedør" i selve
# titlen -- en tekstbaseret "terrassedør"-søgning ville have misset dem,
# mens sitets EGEN kategori-tildeling korrekt fangede dem.
#
# fire_rating beregnes derimod ALTID fra tekst, uanset category_hint -- fordi
# samme kilde også viste det modsatte problem: "Daloc S43 – Brand EL30, lyd
# og sikkerhedsdør" er kategoriseret som "Sikringsdør", IKKE "Branddøre", men
# er reelt brandklassificeret. At stole blindt på kildens kategori ville her
# have tabt en ægte branddør.
TERRASSEDOOR_WORD = re.compile(r"(h[æa]ve)?skyded[øo]r|terrassed[øo]r", re.I)
VINDUE_WORD = re.compile(r"vindue\w*|vinduesparti|ovenlysvindue|glasparti", re.I)


def classify_subtype(title: str, fire_rating: str | None, category_hint: str | None = None) -> str:
    """Returnerer én af: 'brandvindue', 'branddoer', 'terrassedoer', 'vindue',
    'andet'. `category_hint` er én af samme fire (minus 'brandvindue', som
    altid udledes af fire_rating) + 'doer_andet', eller None (tekst-fallback,
    bruges af kilder uden egen kategoristruktur, fx DBA)."""
    if category_hint == "terrassedoer":
        return "terrassedoer"
    if category_hint == "vindue":
        return "brandvindue" if fire_rating else "vindue"
    if category_hint in ("branddoer", "doer_andet"):
        return "branddoer" if fire_rating else "andet"

    # Tekst-fallback: ingen strukturel kategori at stole på.
    t = title or ""
    if TERRASSEDOOR_WORD.search(t):
        return "terrassedoer"
    if VINDUE_WORD.search(t):
        return "brandvindue" if fire_rating else "vindue"
    if _DOOR_WORD.search(t):
        return "branddoer" if fire_rating else "andet"
    return "andet"


def to_dkk(amount: float, currency: str, rates: dict) -> float:
    currency = currency.upper()
    if currency == "DKK":
        return amount
    if currency == "EUR":
        return amount * rates["eur_dkk"]
    if currency == "SEK":
        return amount * rates["sek_dkk"]
    if currency == "NOK":
        return amount * rates["nok_dkk"]
    if currency == "USD":
        return amount * rates["usd_dkk"]
    raise ValueError(f"Ukendt valuta: {currency}")


def normalize_listing(
    *,
    source: str,
    title: str,
    description: str,
    price_amount: float,
    price_currency: str,
    url: str,
    rates: dict,
    extra: dict | None = None,
    origin_country_code: str | None = None,
    import_costs: dict | None = None,
) -> dict:
    text = f"{title} {description}"
    extra = extra or {}

    # Struktureret kilde-data vinder altid over tekstudtræk -- se docstring.
    source_attributes = extra.get("attributes") or {}
    attributes = dict(source_attributes)
    if "width_cm" not in attributes or "height_cm" not in attributes:
        attributes.update(
            {k: v for k, v in extract_dimensions_from_text(text).items() if k not in attributes}
        )
    fire_rating = source_attributes.get("fire_rating") or extract_fire_rating(text)
    if fire_rating:
        attributes["fire_rating"] = fire_rating
    attributes["subtype"] = classify_subtype(title, fire_rating, extra.get("subtype_hint"))

    price_dkk = to_dkk(price_amount, price_currency, rates)
    landed_price_dkk = price_dkk  # ingen import-logik for døre i v1 -- alle fund er danske

    return {
        "source": source,
        "title": title,
        "url": url,
        "price_dkk": price_dkk,
        "landed_price_dkk": landed_price_dkk,
        "shipping_customs_dkk": 0.0,
        "origin_country": origin_country_code,
        "attributes": attributes,
        "raw": extra,
    }
