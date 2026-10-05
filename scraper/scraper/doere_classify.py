"""Klassifikation for kategorien "døre" (SHV-sourcing, se categories.py).

Samme kontrakt som scraper.classify.classify(), men uden en etableret
"god pris"-tærskel endnu -- i modsætning til støvsuger-kategorien har vi
ingen referenceprisliste (models.py's price_new_dkk) for brugte døre. v1
skelner derfor kun mellem "noget konkret at vurdere" (mål og/eller
brandklasse fundet) og "intet at gå efter" -- en hård "køb nu"-dom
kræver en fremtidig prisreference, som endnu ikke findes for denne
kategori.
"""

from __future__ import annotations

import re

# P2 (Opus-review af 935 live DBA-titler, 2026-10-05): 19% af alt med
# eksplicit brand-ordforråd (31 af 159 titler) blev afvist, fordi classify()
# hidtil UDELUKKENDE scorede et NUMERISK brandklassetal (fire_rating) --
# selve ordet "branddør"/"brandvindue"/"brandglas" vejede intet. 28 af de 31
# var ægte branddøre/-vinduer hvor sælgeren ikke skrev et tal ("Branddør",
# "Helt nye brandvinduer", "Branddøre af mærket Safco Doors"). Kun 3 var
# reel støj (to låsebeslag, ét "Brand sikkerhed, 68 grader") -- et nettotab
# accepteret bevidst, se rapportens punkt C. `\s*` mellem "brand" og ordet
# dækker både sammensætning ("branddør") og mellemrum ("brand vinduer",
# faktisk fundet i data).
_BRAND_WORD_PATTERN = re.compile(
    r"brand\s*(d[øo]re?|vindue\w*|glas\w*|parti\w*|element\w*|lem\b)", re.I
)

SELLER_QUESTIONS = [
    "Hvad er dørens eksakte mål (bredde x højde x tykkelse), målt af sælger selv?",
    "Er karmen inkluderet i prisen?",
    "Hvilken retning er døren hængt (venstre/højre ud/ind)?",
    "Er brandklassen (fx BD60) mærket på selve døren eller karmen, ikke kun i annoncen?",
    "Er der synlige skader, slid eller huller fra tidligere montering (fx dørpumpe/greb)?",
]


def classify(listing: dict, config: dict) -> dict:
    attributes = listing.get("attributes") or {}
    has_width = "width_cm" in attributes
    has_height = "height_cm" in attributes
    has_both_dimensions = has_width and has_height
    # P10 (samme review): gren 4 i doere_normalize.py (ét mål uden
    # brandklasse ved siden af) gav altid 0 point her, fordi classify()
    # krævede BÅDE bredde og højde -- i praksis død kode. 2 målte reelle tab:
    # "Sweedoor Hvid indvendig dør 203 cm" og "Hvid terrassedør h 210,8 cm."
    has_one_dimension = has_width != has_height  # XOR: netop ét af de to
    has_fire_rating = bool(attributes.get("fire_rating"))
    has_brand_word = bool(_BRAND_WORD_PATTERN.search(listing.get("title") or ""))

    score = 0
    reasons: list[str] = []
    if has_both_dimensions:
        score += 2
        reasons.append("+2 mål (bredde/højde) kendt")
    elif has_one_dimension:
        score += 1
        reasons.append("+1 kun ét mål kendt (bredde ELLER højde, ikke begge)")
    if has_fire_rating:
        score += 2
        reasons.append(f"+2 brandklasse oplyst ({attributes.get('fire_rating')})")
    if has_brand_word:
        score += 1
        reasons.append("+1 eksplicit brandord i titlen (fx 'branddør'), selv uden tal/klasse")
    if "thickness_cm" in attributes:
        score += 1
        reasons.append("+1 tykkelse oplyst")

    mangler_info: list[str] = []
    if has_one_dimension:
        mangler_info.append("kun ét mål (bredde ELLER højde) kendt, det andet kan ikke bekræftes")
    elif not has_both_dimensions:
        mangler_info.append("bredde/højde kan ikke bekræftes ud fra annoncens tekst")
    if not has_fire_rating:
        mangler_info.append(
            "ingen brandklasse (BD/EI) fundet -- relevant kun for brandsikre døre/vinduer"
        )

    has_any_dimension = has_both_dimensions or has_one_dimension
    if not has_any_dimension and not has_fire_rating and not has_brand_word:
        return _result(
            "afvis",
            score,
            reasons,
            ["intet mål eller brandklasse-omtale -- intet konkret at vurdere"],
            method="afvist: intet identificerbart signal",
        )

    return _result(
        "se nærmere",
        score,
        reasons,
        mangler_info,
        method="se nærmere: mål/brandklasse fundet, ingen etableret prisreference endnu",
    )


def _result(
    vurdering: str, score: int, reasons: list[str], mangler_info: list[str], *, method: str
) -> dict:
    return {
        "vurdering": vurdering,
        "score": score,
        "score_reasons": reasons,
        "mangler_info": mangler_info,
        "classification_method": method,
        "spoergsmaal_til_saelger": list(SELLER_QUESTIONS) if vurdering == "se nærmere" else [],
    }
