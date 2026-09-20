"""Udtræk model/støvklasse/bløde signaler fra rå annoncetekst, konverter til DKK.

to_dkk()/compute_landed_price_dkk() er ported uændret fra PASPEAKERS' normalize.py
(samme landed-cost-mekanik, kun feltnavne uændrede) -- se den fils docstring for
hvorfor et bevidst IKKE-forsøgt "gæt" på gebyrer for EU-sælgere er korrekt.
"""

from __future__ import annotations

import re

from .models import (
    EXPLICIT_CLASS_PATTERN,
    HARD_REJECT_PATTERNS,
    KNOWN_BRANDS,
    MODEL_WHITELIST,
    WEAK_EVIDENCE_PATTERN,
)

_KNOWN_BRAND_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(b) for b in KNOWN_BRANDS) + r")\b", re.I
)


def mentions_known_brand(text: str) -> bool:
    """True hvis et kendt sikkerhedsstøvsuger-mærke (models.py's
    MODEL_WHITELIST) nævnes, SELVOM ingen specifik model matchede. Bruges til
    at nedgradere 'kun svag evidens' fra AFVIS til SE NÆRMERE -- se
    models.py's KNOWN_BRANDS-docstring for det konkrete produktionsfund der
    motiverede dette (rigtige Nilfisk Attix-annoncer med et modelnummer
    whitelisten ikke dækkede endnu, forkert auto-afvist)."""
    return bool(_KNOWN_BRAND_PATTERN.search(text))

# Tilbehør/udlejning/søges/reservedele/manual -- IKKE salg af en hel maskine.
# Dækker dansk/engelsk/tysk/svensk, samme princip som PASPEAKERS' ACCESSORY_
# OR_RENTAL_PATTERN men med støvsuger-specifikt ordforråd (filter/slange/
# poser alene, ikke selve maskinen).
ACCESSORY_OR_RENTAL_PATTERN = re.compile(
    r"\b("
    r"kun\s+filter|filter\s+til\s+salg|filterelement\s+til\s+salg|"
    r"kun\s+slange|slange\s+til\s+salg|"
    r"(?:kun\s+)?(?:sikkerheds)?filterposer?\s+(?:til\s+salg|sælges)|"
    # KRITISK FUND (bruger diskvalificerede fund 2026-09-19): "Kärcher
    # støvsuger poser" (generiske støvsugerposer, ikke "filterposer") blev
    # ikke fanget af mønsteret ovenfor, som kun matcher "(sikkerheds)filter-
    # poser" -- tilføjet bredere match for almindelige støvsugerposer.
    r"st[øo]vsuger(?:s)?\s*poser?\b|poser\s+til\s+st[øo]vsuger|"
    r"reservedele?|ersatzteile?|reserv?del(?:ar)?|"
    r"udlejning|leje\b|til\s*leje|verleih|vermietung|miete[nt]?|uthyrning|hyra|hyr\b|for\s*rent|rental|"
    r"s[øo]ges|sucht|gesucht|wanted|k[øo]bes|k[öo]pes|"
    r"manual|brugsanvisning|bedienungsanleitung|handbog|owners?\s*manual|"
    r"tilbeh[øo]r\s+til\b"  # "tilbehør til Kärcher..." -- selve tilbehøret, ikke maskinen
    r")\b",
    re.I,
)

# Battery/akku-signaler (spec: batterimaskiner kun sekundært, kræver 230V/
# ledning som hovedregel).
BATTERY_PATTERN = re.compile(r"\b(batteri|akku|cordless|18\s*v\b|36\s*v\b)\b", re.I)
CORDED_PATTERN = re.compile(r"\b(230\s*v|ledning|kabel|corded|netdrevet)\b", re.I)

# R8 (Opus 5-gennemgang, 2026-09-20): to Nilfisk AERO 26-2H PC-forhandler-
# annoncer ("NU KUN 2.995 KR.", fabriksnye/ubrugte) blev fejlagtigt afvist,
# fordi classify.py lagde filterestimatet (700-900 kr., spec: "på ENHVER
# BRUGT maskine") oveni selv for åbenlyst ubrugte/nye maskiner.
UNUSED_MACHINE_PATTERN = re.compile(
    r"\b(fabriksny\w*|helt\s+ny\w*|ubrugt\w*|ny\s+i\s+kasse|ungebraucht|nagelneu|oanv[äa]nd\w*)\b",
    re.I,
)

# Automatisk/semiautomatisk filterrensning -- spec's egen keyword-liste
# ("Tact, AFC, XC, PC, InfiniClean, AirBoost") udvidet med de øvrige
# producent-navne set i modelnavnene (MPB, Safe EW, iPulse).
FILTER_CLEANING_PATTERN = re.compile(
    r"\b(tact|afc|\bxc\b|\bpc\b|infiniclean|airboost|\bmpb\b|safe\s*ew|ipulse)\b", re.I
)
MANUAL_CLEANING_PATTERN = re.compile(
    r"\b(manuel\s+rens|ryst(?:es|er)?\s+manuelt|manual\s+shak)", re.I
)

FLOWSENSOR_PATTERN = re.compile(r"\b(flowsensor|flow[\s-]*sensor|volumenstr[øo]m)\b", re.I)
STIKDAASE_PATTERN = re.compile(
    r"\b(stikd[åa]se|autostart|automatikstartdose|power\s*take\s*off|werkzeugsteckdose)\b", re.I
)
ANTISTATIC_HOSE_PATTERN = re.compile(r"\bantistatisk\w*\s+slange|antistatik\w*\s*schlauch\b", re.I)
NEW_FILTER_PATTERN = re.compile(
    r"\b(nyt?\s+(?:h-?)?filter(?:element)?|skiftet\s+filter|nyligt\s+skiftet\s+filter|"
    r"neu(?:er)?\s+filter)\b",
    re.I,
)
UNUSED_BAGS_PATTERN = re.compile(
    r"\b(ubrugte\s+(?:sikkerheds)?filterposer|nye\s+(?:sikkerheds)?filterposer|"
    r"uge[øo]bnede?\s+poser)\b",
    re.I,
)

# Spec: "-3 Billeder viser slidt/manglende filter eller revnede pakninger" --
# tekst-proxy for billed-evidens, da vi kun scraper tekst.
CONDITION_RED_FLAG_PATTERN = re.compile(
    r"\b(slidt\s+filter|manglende\s+filter|mangler\s+filter|uden\s+filter|"
    r"revnet\w*\s+pakning\w*|defekt\w*\s+pakning\w*|i\s+stykker)\b",
    re.I,
)
ASBESTOS_USED_PATTERN = re.compile(
    r"\b(har\s+k[øo]rt\s+asbest|brugt\s+(?:til|med)\s+asbest|asbestarbejde\s+udf[øo]rt)\b", re.I
)
ASBESTOS_APPROVED_TEXT_PATTERN = re.compile(
    r"\b(asbestgodkendt|trgs\s*519|asbestzugelassen|asbest[\s-]*certificeret)\b", re.I
)
COMPLETENESS_NEGATIVE_PATTERN = re.compile(
    r"\b(kun\s+beholder|uden\s+slange|l[øo]sdele|mangler\s+motorhoved|kun\s+motorhoved)\b", re.I
)


def is_accessory_or_rental(text: str) -> bool:
    return bool(ACCESSORY_OR_RENTAL_PATTERN.search(text or ""))


# R4 (Opus 5-gennemgang, 2026-09-20): ACCESSORY_OR_RENTAL_PATTERN ovenfor
# kører bevidst SNÆVERT på titel+beskrivelse tilsammen, fordi en bredere
# pose-/børste-/dyse-scanning der ALTID afviser ville dræbe ægte
# maskinannoncer der nævner "+1 ubrugte sikkerhedsfilterposer medfølger"
# (et scoring-plus, se classify.py) i beskrivelsen. Løsningen er et
# SEPARAT, kun-titel-scoped mønster: hvis TITLENS hovedvare er tilbehør
# (ikke bare nævnt i teksten et sted), OG titlen ikke i sig selv matcher en
# whitelistet model, er det med stor sikkerhed en tilbehørs-/reservedele-
# annonce. Fundet i live data: "Nilfisk poser", "Nilfisk børste , Nilfisk",
# "Nilfisk Filterpose til Attix 751/761/961", "Nilfisk Alto ATTIX 7 Liquid
# slangesæt".
ACCESSORY_TITLE_PATTERN = re.compile(
    r"\b(pose[rn]?|filterpose[rn]?|st[øo]vsugerpose[rn]?|b[øo]rste[rn]?|"
    r"mundstykke[rn]?|slanges[æa]t|d[yø]se[rn]?|filterelement(?:er)?|"
    r"kulfilter|hjuls[æa]t|adapter|bags?|nozzle|brush)\b",
    re.I,
)


def is_accessory_title(title: str) -> bool:
    """True hvis titlens hovedvare er tilbehør (pose/børste/dyse/slangesæt
    osv.) OG titlen ikke selv matcher en whitelistet hel-maskine-model.
    Kører KUN på titlen (se modulets kommentar ovenfor for hvorfor)."""
    if not ACCESSORY_TITLE_PATTERN.search(title or ""):
        return False
    return classify_model(title or "").get("model_key") is None


# R5 (Opus 5-gennemgang, 2026-09-20): mentions_known_brand() alene gav en
# for bred fribillet -- "Bosch støvsuger" og "Nilfisk støvsuger" (INTET
# modelnummer, intet at bede sælger bekræfte) endte forkert i "se nærmere"
# i stedet for at blive afvist som støj. Et kendt mærke bør kun beskytte
# mod auto-afvisning når der OGSÅ er et modelnummer-agtigt tal at
# verificere -- ikke bare en pris/watt/volt/liter-specifikation.
_SPEC_UNIT_PATTERN = re.compile(
    r"\b\d{1,5}\s*(?:w(?:att)?|v(?:olt)?|l(?:iter)?|kr|stk|cm|mm|mtr|m|%|"
    r"[åa]r|kg|bar|db|hk|rpm)\b",
    re.I,
)
_MODEL_TOKEN_PATTERN = re.compile(r"\d{2,4}")


def has_model_token(text: str) -> bool:
    """True hvis teksten indeholder et tal der IKKE blot er en kendt
    specifikation (watt/volt/liter/pris/...) -- dvs. et tal der plausibelt
    er en del af et modelnavn. Uden et sådant er der intet konkret at spørge
    sælger om ud over de faste standardspørgsmål."""
    stripped = _SPEC_UNIT_PATTERN.sub(" ", text or "")
    return bool(_MODEL_TOKEN_PATTERN.search(stripped))


def classify_model(text: str) -> dict:
    """Finder model i teksten (WHITELIST tjekkes altid FØR HARD_REJECT_PATTERNS
    -- se models.py's docstring for hvorfor rækkefølgen selv er garantien for
    at en whitelistet model aldrig fejlagtigt rammes af et bredere
    blacklist-mønster).

    Returnerer altid disse nøgler (også ved intet fund):
      model_key, brand, model_label, dust_class, klasse_kilde,
      container_l, asbestos_approved, battery, hard_reject, reject_reason
    """
    for m in MODEL_WHITELIST:
        if m.pattern.search(text):
            return {
                "model_key": m.key,
                "brand": m.brand,
                "model_label": m.label,
                "dust_class": m.dust_class,
                "klasse_kilde": "modelnavn",
                "container_l": m.container_l,
                "price_new_dkk_low": m.price_new_dkk_low,
                "price_new_dkk_high": m.price_new_dkk_high,
                "asbestos_approved": m.asbestos_approved,
                "battery": m.battery,
                "hard_reject": False,
                "reject_reason": None,
            }

    for reason, pattern in HARD_REJECT_PATTERNS:
        if pattern.search(text):
            return {
                "model_key": None,
                "brand": None,
                "model_label": None,
                "dust_class": "ingen (L/ukendt)",
                "klasse_kilde": None,
                "container_l": None,
                "price_new_dkk_low": None,
                "price_new_dkk_high": None,
                "asbestos_approved": None,
                "battery": False,
                "hard_reject": True,
                "reject_reason": reason,
            }

    # Intet model-match -- prøv eksplicit klasse-udsagn i selve teksten
    # ("støvklasse H"), svagere end et modelmatch (klasse_kilde=annoncetekst,
    # ikke modelnavn) men stærkere end ingenting.
    m = EXPLICIT_CLASS_PATTERN.search(text)
    if m:
        return {
            "model_key": None,
            "brand": None,
            "model_label": None,
            "dust_class": m.group(1).upper(),
            "klasse_kilde": "annoncetekst",
            "container_l": None,
            "price_new_dkk_low": None,
            "price_new_dkk_high": None,
            "asbestos_approved": None,
            "battery": bool(BATTERY_PATTERN.search(text)),
            "hard_reject": False,
            "reject_reason": None,
        }

    return {
        "model_key": None,
        "brand": None,
        "model_label": None,
        "dust_class": "ukendt",
        "klasse_kilde": None,
        "container_l": None,
        "price_new_dkk_low": None,
        "price_new_dkk_high": None,
        "asbestos_approved": None,
        "battery": bool(BATTERY_PATTERN.search(text)),
        "hard_reject": False,
        "reject_reason": None,
    }


def extract_soft_signals(text: str) -> dict:
    """Tekst-baserede bløde signaler til scoring (classify.py) -- se spec's
    point-tabel. Alt her er BOOLEAN "nævnt i teksten", ikke en garanti (samme
    forbehold som spec selv gør: "kunne verificeres")."""
    filter_cleaning = "ukendt"
    if FILTER_CLEANING_PATTERN.search(text):
        filter_cleaning = "automatisk"
    elif MANUAL_CLEANING_PATTERN.search(text):
        filter_cleaning = "manuel"

    return {
        "filterrensning": filter_cleaning,
        "flowsensor": True if FLOWSENSOR_PATTERN.search(text) else "ukendt",
        "stikdaase": True if STIKDAASE_PATTERN.search(text) else "ukendt",
        "antistatisk_slange": bool(ANTISTATIC_HOSE_PATTERN.search(text)),
        "nyt_filter": bool(NEW_FILTER_PATTERN.search(text)),
        "unused_machine": bool(UNUSED_MACHINE_PATTERN.search(text)),
        "ubrugte_poser": bool(UNUSED_BAGS_PATTERN.search(text)),
        "condition_red_flag": bool(CONDITION_RED_FLAG_PATTERN.search(text)),
        "asbest_kort_i_brug": bool(ASBESTOS_USED_PATTERN.search(text)),
        "asbest_godkendt_i_tekst": bool(ASBESTOS_APPROVED_TEXT_PATTERN.search(text)),
        "completeness_negative": bool(COMPLETENESS_NEGATIVE_PATTERN.search(text)),
        "weak_evidence_only": bool(WEAK_EVIDENCE_PATTERN.search(text)),
        "known_brand_mentioned": mentions_known_brand(text) and has_model_token(text),
        "corded_mentioned": bool(CORDED_PATTERN.search(text)),
        "battery_mentioned": bool(BATTERY_PATTERN.search(text)),
        "medfoelger": _extract_accessories(text),
    }


_ACCESSORY_PATTERNS = {
    "slange": re.compile(r"\b(slange|schlauch|hose)\b", re.I),
    "filter": re.compile(r"\b(filter(?:element)?)\b", re.I),
    "poser": re.compile(
        r"\b((?:sikkerheds)?filterposer?|safety\s*bags?|sicherheitsfilterbeutel)\b", re.I
    ),
}


def _extract_accessories(text: str) -> list[str]:
    return [name for name, pat in _ACCESSORY_PATTERNS.items() if pat.search(text)]


def to_dkk(amount: float, currency: str, rates: dict) -> float:
    currency = currency.upper()
    if currency == "DKK":
        return amount
    if currency == "EUR":
        return amount * rates["eur_dkk"]
    if currency == "SEK":
        return amount * rates["sek_dkk"]
    if currency == "USD":
        return amount * rates["usd_dkk"]
    raise ValueError(f"Ukendt valuta: {currency}")


def compute_landed_price_dkk(
    price_dkk: float, origin_country_code: str | None, import_costs: dict
) -> tuple[float, float]:
    """Ported uændret fra PASPEAKERS' normalize.py -- se den fils docstring."""
    eu_codes = set(import_costs.get("eu_country_codes", []))
    if origin_country_code is None or origin_country_code.upper() in eu_codes:
        return price_dkk, 0.0

    shipping_dkk = import_costs["default_shipping_dkk"]
    eur_dkk = import_costs.get("_eur_dkk_rate", 1.0)
    customs_value_dkk = price_dkk + shipping_dkk
    duty_threshold_dkk = import_costs["duty_threshold_eur"] * eur_dkk

    over_threshold = customs_value_dkk > duty_threshold_dkk
    duty_dkk = customs_value_dkk * (import_costs["duty_pct"] / 100) if over_threshold else 0.0
    vat_dkk = (customs_value_dkk + duty_dkk) * (import_costs["vat_pct"] / 100)

    shipping_customs_dkk = shipping_dkk + duty_dkk + vat_dkk
    return price_dkk + shipping_customs_dkk, shipping_customs_dkk


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
    """Bygger et normaliseret listing-dict klar til scoring/dedup.

    Model/støvklasse prioriterer titlen (mere pålidelig, sælger-skrevet
    kort form) men falder tilbage til hele teksten (titel+beskrivelse) hvis
    titlen intet match har -- samme princip som PASPEAKERS' normalize.py."""
    text = f"{title} {description}"

    model_info = classify_model(title)
    if model_info["dust_class"] == "ukendt":
        model_info = classify_model(text)
    soft = extract_soft_signals(text)

    price_dkk = to_dkk(price_amount, price_currency, rates)

    if import_costs is not None:
        import_costs = {**import_costs, "_eur_dkk_rate": rates["eur_dkk"]}
        landed_price_dkk, shipping_customs_dkk = compute_landed_price_dkk(
            price_dkk, origin_country_code, import_costs
        )
    else:
        landed_price_dkk, shipping_customs_dkk = price_dkk, 0.0

    return {
        "source": source,
        "title": title,
        "url": url,
        "price_dkk": price_dkk,
        "landed_price_dkk": landed_price_dkk,
        "shipping_customs_dkk": shipping_customs_dkk,
        "origin_country": origin_country_code,
        **model_info,
        **soft,
        "raw": extra or {},
    }
