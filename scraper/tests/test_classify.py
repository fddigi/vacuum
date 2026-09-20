"""Kritisk test af scoring/vurdering-motoren -- syntetiske listings, ingen
HTTP-mocking (samme princip som PASPEAKERS' test_pipeline_last_seen.py: kun
forretningslogikken nedstrøms for fetch() testes)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.classify import classify
from scraper.normalize import classify_model, extract_soft_signals

TEST_CONFIG = {
    "filter_replacement_estimate_dkk": 800,
    "prislofter": {
        "kompakt_h": {"koeb_max": 3500, "god_handel_max": 2500},
        "stor_h": {"koeb_max": 5000, "god_handel_max": 3500},
        "m_klasse": {"koeb_max": 2000, "god_handel_max": 1200},
    },
}


def _listing(title: str, description: str, price_dkk: float) -> dict:
    model_info = classify_model(title)
    if model_info["dust_class"] == "ukendt":
        model_info = classify_model(f"{title} {description}")
    soft = extract_soft_signals(f"{title} {description}")
    return {
        "title": title,
        "landed_price_dkk": price_dkk,
        **model_info,
        **soft,
    }


def test_koeb_nu_requires_god_handel_price_and_verified_class():
    listing = _listing(
        "Kärcher NT 35/1 Tact Te H sælges, komplet med slange og filter",
        "Automatisk Tact-filterrensning, FlowSensor, antistatisk slange, nyt filter",
        1500,  # under god_handel_max (2500) for kompakt_h, + filter-estimat undgås (nyt_filter)
    )
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "køb nu", result
    assert result["score"] >= 5
    assert result["mangler_info"] == []
    assert result["spoergsmaal_til_saelger"] == []


def test_price_above_koeb_loft_is_afvist_not_se_naermere():
    listing = _listing(
        "Kärcher NT 35/1 Tact Te H sælges",
        "Pæn stand",
        5000,  # langt over koeb_max=3500 for kompakt_h (25 l)
    )
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "afvis"
    assert "prisloft" in result["mangler_info"][-1] or "over" in " ".join(result["mangler_info"])


def test_price_between_god_handel_and_koeb_is_se_naermere():
    listing = _listing(
        "Kärcher NT 35/1 Tact Te H sælges",
        "Pæn stand, ingen yderligere detaljer",
        # 2000 + filter-estimat (800, da nyt_filter ikke er nævnt) = 2800,
        # mellem god_handel_max (2500) og koeb_max (3500) for kompakt_h.
        2000,
    )
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "se nærmere"
    assert result["spoergsmaal_til_saelger"] == [
        "Billede af typeskiltet bag på eller under motorhovedet",
        "Står der L, M eller H på typeskiltet eller advarselsmærkaten?",
        "Hvornår er filterelementet sidst skiftet, og er det originalt?",
        "Giver flowalarmen lyd, når slangen dækkes til?",
        "Har maskinen kørt asbest?",
        "Medfølger der sikkerhedsfilterposer?",
    ]


def test_hard_blacklist_model_is_always_afvist_regardless_of_price():
    listing = _listing("Kärcher NT 35/1 Tact Te sælges", "Meget billig, kun 200 kr", 200)
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "afvis"
    assert "afvisning" in result["classification_method"]


def test_weak_evidence_only_is_afvist():
    listing = _listing(
        "Professionel byggestøvsuger, industristøvsuger",
        "HEPA 14 filter, 99,97% effektivitet",
        1000,
    )
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "afvis"


def test_weak_evidence_with_known_brand_is_se_naermere_not_afvis():
    """Regression -- fundet ved live test 2026-09-19 mod dba.dk (og siden
    strammet af en Opus 5-gennemgang 2026-09-20, se test_normalize.py's
    test_nilfisk_attix_without_class_letter_is_hard_rejected): et Attix-
    modelnummer UDEN klassebogstav (fx "751-11") er nu selv en kendt fælde
    og hård-afvises korrekt. Denne test dækker i stedet den resterende,
    ægte gråzone: et Attix-modelnummer MED et H, som models.py's whitelist
    blot ikke har den præcise variant af endnu ("44-0H" findes ikke, kun
    "44-2H") -- her SKAL et kendt mærke stadig give 'se nærmere', ikke
    afvises, da vi ikke kan udelukke det er en reel H-model."""
    listing = _listing(
        "Nilfisk Attix 44-0H industristøvsuger blå", "Pæn stand", 2000
    )
    assert listing["dust_class"] == "ukendt"  # præcis denne variant er IKKE i whitelisten
    assert listing["known_brand_mentioned"] is True
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "se nærmere"
    assert any("typeskiltet" in m for m in result["mangler_info"])


def test_battery_machine_can_never_reach_koeb_nu():
    """Spec: batterimaskiner kun sekundært fund -- selv med perfekt pris og
    fuld score må resultatet aldrig blive 'køb nu'."""
    listing = _listing(
        "Starmix ISC 1625 MPB H batteri sælges komplet",
        "Automatisk Tact-rens, FlowSensor, stikdåse, antistatisk slange, nyt filter",
        500,
    )
    assert listing["battery"] is True
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] != "køb nu"
    assert any("batterimaskine" in m for m in result["mangler_info"])


def test_unconfirmed_m_class_from_text_only_capped_at_se_naermere():
    """M-klasse uden model-match (kun tekst-udsagn) kan ikke bekræfte
    asbest-udelukkelse -- må aldrig automatisk blive 'køb nu'."""
    listing = _listing("Byggestøvsuger, støvklasse M, ukendt mærke, meget billig", "God stand", 500)
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] != "køb nu"
    assert any("asbest" in m.lower() for m in result["mangler_info"])


def test_hilti_penalty_applied_and_visible_in_score_reasons():
    listing = _listing("Hilti VC 40H-X sælges", "Pæn stand, komplet", 1500)
    result = classify(listing, TEST_CONFIG)
    assert any("Hilti" in r for r in result["score_reasons"])
    assert result["score"] <= 0  # -5 Hilti-straf skal dominere evt. positive point


def test_completeness_negative_is_afvist():
    listing = _listing("Kärcher NT 35/1 Tact Te H løsdele", "Kun beholder, uden slange", 500)
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "afvis"


def test_unknown_container_size_does_not_crash_and_flags_missing_info():
    """En whitelistet model UDEN kendt beholderstørrelse (fx Protool VCP 260
    E-H, container_l=None i models.py) skal ikke crashe prisloft-logikken."""
    listing = _listing("Protool VCP 260 E-H sælges", "Pæn stand", 1000)
    assert listing["container_l"] is None
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] in (
        "se nærmere",
        "afvis",
        "køb nu",
    )  # må bare ikke kaste en exception
    assert any("beholderstørrelse" in m for m in result["mangler_info"])


def test_new_price_70pct_ceiling_overrides_category_ceiling():
    """Nilfisk AERO 26-2H PC har kendt nypris 3100-3500 kr. i models.py ->
    70% = 2170-2450 kr. Selv en pris UNDER kompakt_h's koeb_max (3500) skal
    afvises hvis den overstiger 70% af den KENDTE nypris."""
    listing = _listing("Nilfisk AERO 26-2H PC sælges", "Pæn stand", 3000)
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "afvis"
    assert "70%" in " ".join(result["mangler_info"])


def test_zero_signal_listing_is_afvist_not_se_naermere():
    """Regression -- fundet 2026-09-19: bare 'Støvsuger'-annoncer (intet
    mærke, ingen klasse-omtale, ikke engang svag markedsføringstekst) endte
    i 'se nærmere' og blev manuelt diskvalificeret af brugeren ni gange i
    træk. Sådanne annoncer giver intet at handle på og bør afvises direkte."""
    for title in ["Støvsuger", "støvsuger", "Lille pæn ting"]:
        listing = _listing(title, "", 75)
        result = classify(listing, TEST_CONFIG)
        assert result["vurdering"] == "afvis", f"{title!r}: {result}"
        assert result["classification_method"] == "afvist: intet identificerbart signal"


def test_known_brand_still_protects_from_zero_signal_afvis():
    """Modstykke til testen ovenfor: et KENDT mærke MED et modelnummer,
    der har et H men ikke er i whitelisten endnu, skal STADIG give
    'se nærmere', ikke det nye 'intet signal'-afvis. "751-11" (ingen
    klassebogstav) er BEVIDST ikke brugt her -- den er nu korrekt
    hård-afvist af models.py's "Attix uden klassebogstav"-regel (Opus 5,
    2026-09-20), en helt separat og tidligere port i classify.py."""
    listing = _listing("Nilfisk Attix 44-0H industristøvsuger blå", "Pæn stand", 2000)
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "se nærmere"


def test_70pct_rule_uses_raw_price_not_price_plus_filter_estimate():
    """Regression -- brugerens eget 'billigst forsvarligt'-eksempel (Metabo
    ASA 30 H PC, nypris 2.349 kr.): før denne rettelse blev 70%-tjekket
    lavet på (pris + 800 kr. filterestimat), hvilket gjorde selv en fair
    brugt-pris (1.500 kr.) til en automatisk afvisning, fordi 2.300 kr. >
    70% af 2.349 kr. Nu tjekkes selve udbudsprisen alene."""
    config = {**TEST_CONFIG, "prislofter": {**TEST_CONFIG["prislofter"]}}
    listing = _listing(
        "Metabo ASA 30 H PC sælges, komplet med slange og filter", "", 1500
    )
    assert listing["price_new_dkk_low"] == 2349
    result = classify(listing, config)
    assert result["vurdering"] != "afvis", result
    assert "70%" not in " ".join(result["mangler_info"])


def test_70pct_rule_skipped_entirely_for_confirmed_unused_machine():
    """Regression -- en bekræftet fabriksny/ubrugt maskine skal IKKE
    sammenlignes mod en brøkdel af sin egen nypris (reglen forudsætter
    slid/afskrivning på en BRUGT maskine, en kategorifejl for en ny en).
    'Nilfisk AERO 26-2H PC NU KUN 2.995 KR, fabriksny' (nypris 3.100-3.500)
    blev tidligere afvist alene på 70%-reglen."""
    listing = _listing(
        "Nilfisk AERO 26-2H PC NU KUN 2.995 KR fabriksny", "", 2995
    )
    assert listing["unused_machine"] is True
    result = classify(listing, TEST_CONFIG)
    assert "70%" not in " ".join(result["mangler_info"])
    assert result["classification_method"] != "afvist: over 70%-af-nypris-loftet"


def test_filter_estimate_skipped_for_unused_machine_but_not_used_one():
    """R8 -- filterestimatet (700-900 kr.) gælder kun BRUGTE maskiner (spec:
    'på enhver BRUGT maskine'). Pris valgt så kun den ubrugte lander i/under
    'god handel' (kompakt_h god_handel_max=2500): 1.800 alene vs.
    1.800+800=2.600 med tillæg."""
    common_desc = "Automatisk Tact-rens, FlowSensor, stikdåse, antistatisk slange"
    unused = _listing("Nilfisk Attix 30-0H PC, fabriksny, ubrugt", common_desc, 1800)
    used = _listing("Nilfisk Attix 30-0H PC, brugt men fin stand", common_desc, 1800)
    assert unused["unused_machine"] is True
    assert used["unused_machine"] is False

    unused_result = classify(unused, TEST_CONFIG)
    used_result = classify(used, TEST_CONFIG)
    assert unused_result["vurdering"] == "køb nu"
    assert used_result["vurdering"] == "se nærmere"
