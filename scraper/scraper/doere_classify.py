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

SELLER_QUESTIONS = [
    "Hvad er dørens eksakte mål (bredde x højde x tykkelse), målt af sælger selv?",
    "Er karmen inkluderet i prisen?",
    "Hvilken retning er døren hængt (venstre/højre ud/ind)?",
    "Er brandklassen (fx BD60) mærket på selve døren eller karmen, ikke kun i annoncen?",
    "Er der synlige skader, slid eller huller fra tidligere montering (fx dørpumpe/greb)?",
]


def classify(listing: dict, config: dict) -> dict:
    attributes = listing.get("attributes") or {}
    has_dimensions = "width_cm" in attributes and "height_cm" in attributes
    has_fire_rating = bool(attributes.get("fire_rating"))

    score = 0
    reasons: list[str] = []
    if has_dimensions:
        score += 2
        reasons.append("+2 mål (bredde/højde) kendt")
    if has_fire_rating:
        score += 2
        reasons.append(f"+2 brandklasse oplyst ({attributes.get('fire_rating')})")
    if "thickness_cm" in attributes:
        score += 1
        reasons.append("+1 tykkelse oplyst")

    mangler_info: list[str] = []
    if not has_dimensions:
        mangler_info.append("bredde/højde kan ikke bekræftes ud fra annoncens tekst")
    if not has_fire_rating:
        mangler_info.append(
            "ingen brandklasse (BD/EI) fundet -- relevant kun for brandsikre døre/vinduer"
        )

    if not has_dimensions and not has_fire_rating:
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
