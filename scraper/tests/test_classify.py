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
    """Regression -- fundet ved live test 2026-09-19 mod dba.dk: rigtige
    Nilfisk Attix-annoncer med et modelnummer models.py IKKE dækker (fx
    "Attix 751-11", "Attix 965-21 DC XC") blev fejlagtigt hård-afvist bare
    fordi ordet 'industristøvsuger' indgår i teksten. Et kendt mærke er en
    reel grund til at bede om et typeskilt, ikke til automatisk at afvise."""
    listing = _listing(
        "Nilfisk Attix 751-11 industristøvsuger blå", "Pæn stand", 2000
    )
    assert listing["dust_class"] == "ukendt"  # modelnummeret er IKKE i whitelisten
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
    """Modstykke til testen ovenfor: et KENDT mærke (uden model-match) skal
    STADIG give 'se nærmere', ikke det nye 'intet signal'-afvis -- ellers
    ville den tidligere rettede Nilfisk Attix-sag (se test_normalize.py)
    blive ramt igen af en anden regel."""
    listing = _listing("Nilfisk Attix 751-11 industristøvsuger blå", "Pæn stand", 2000)
    result = classify(listing, TEST_CONFIG)
    assert result["vurdering"] == "se nærmere"
