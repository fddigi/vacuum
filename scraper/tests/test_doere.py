"""Regressionstest for døre-kategorien (doere_normalize.py/doere_classify.py)
-- se categories.py's docstring for hvorfor denne kategori findes, og
doere_normalize.py's docstring for hvorfor struktureret kilde-data altid
vinder over fritekst-udtræk."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.doere_classify import classify
from scraper.doere_normalize import (
    extract_dimensions_from_text,
    extract_fire_rating,
    is_accessory_or_rental,
    is_accessory_title,
    normalize_listing,
)

RATES = {"eur_dkk": 7.46, "sek_dkk": 0.70, "nok_dkk": 0.64, "usd_dkk": 6.90}


def test_structured_source_attributes_win_over_text_extraction():
    """genbyg.py leverer strukturerede mål via extra['attributes'] -- disse
    skal bruges direkte, ikke genudregnes fra titlen."""
    listing = normalize_listing(
        source="genbyg",
        title="BD60 branddør uden karm",
        description="",
        price_amount=1500.0,
        price_currency="DKK",
        url="https://genbyg.dk/x",
        rates=RATES,
        extra={"attributes": {"width_cm": 92.7, "height_cm": 205.5, "thickness_cm": 6.4}},
    )
    # fire_rating udtrækkes altid fra titlen (genbyg's specs-felter har
    # ingen brandklasse) -- kun width/height/thickness kommer fra kilden.
    assert listing["attributes"] == {
        "width_cm": 92.7,
        "height_cm": 205.5,
        "thickness_cm": 6.4,
        "fire_rating": "BD60",
    }


def test_text_fallback_used_when_source_has_no_structured_attributes():
    """DBA-stil annoncer har ingen struktureret kilde-data -- mål skal
    udtrækkes fra selve titlen i stedet."""
    listing = normalize_listing(
        source="dba",
        title="Indvendig dør 82x204 cm, hvid",
        description="",
        price_amount=500.0,
        price_currency="DKK",
        url="https://dba.dk/x",
        rates=RATES,
        extra={},
    )
    assert listing["attributes"]["width_cm"] == 82.0
    assert listing["attributes"]["height_cm"] == 204.0


def test_fire_rating_extracted_from_title_text():
    assert extract_fire_rating("BD60 branddør uden karm") == "BD60"
    assert extract_fire_rating("Brandglas EI60 mål 55 x 240 cm") == "EI60"
    assert extract_fire_rating("Almindelig indvendig dør") is None


def test_mm_written_without_unit_is_recovered_not_rejected():
    """Sælgere skriver ofte mål i mm uden at angive enheden -- en værdi
    >= 400 kan aldrig være cm for en dør, og tolkes derfor som mm (/10),
    PR. VÆRDI, ikke pr. match (se doere_normalize.py's docstring for hvorfor
    en fælles skalering af et blandet mål som 'b: 825 h: 204' er forkert)."""
    assert extract_dimensions_from_text("Dør 890x2075 mm") == {
        "width_cm": 89.0,
        "height_cm": 207.5,
    }
    assert extract_dimensions_from_text("Dør 89x209 cm") == {"width_cm": 89.0, "height_cm": 209.0}


def test_orientation_is_corrected_using_the_door_height_window():
    """Sælgere skriver ofte højde FØRST ('204 x 82 cm') -- den værdi der
    ligger i dørhøjde-vinduet (150-285 cm) vindes altid som højden,
    uafhængigt af hvilken position den stod i teksten."""
    assert extract_dimensions_from_text("Doorline branddør hvid 204 x 82 cm") == {
        "width_cm": 82.0,
        "height_cm": 204.0,
    }


def test_accessory_titles_excluded():
    assert is_accessory_title("Dørgreb i messing, sælges")
    assert is_accessory_title("Hængsler til dør, 4 stk")
    assert not is_accessory_title("BD60 branddør uden karm")


def test_whole_door_with_included_hardware_is_not_an_accessory():
    """RETTET 2026-10-04 (samme lektie som normalize.py's R11, se
    doere_normalize.py's docstring): den oprindelige pattern afviste disse
    fordi den matchede beslags-ordet uanset kontekst -- men hver af disse er
    en HEL dør, hvor beslaget bare er en del af salget. Konkrete titler fra
    research mod dba.dk, 2026-10-04."""
    assert not is_accessory_title("Grå indvendig dør 945x2120mm - H med dørpumpe")
    assert not is_accessory_title("Hvid indvendig dør med håndtag inkl. karm 80x208,6 cm")
    assert not is_accessory_title("Klassisk afsyret fyldningsdør i fyrretræ m. hængsler")
    assert not is_accessory_title("Hvid branddør med lås og hængsler")


def test_accessory_or_rental_text_excluded():
    assert is_accessory_or_rental("Udlejning af dør til byggeprojekt")
    assert is_accessory_or_rental("Dørhåndtag søges")
    assert not is_accessory_or_rental("BD60 branddør uden karm, 1.500 kr.")


def test_classify_afviser_when_nothing_concrete_found():
    listing = {"attributes": {}}
    result = classify(listing, {})
    assert result["vurdering"] == "afvis"
    assert result["classification_method"] == "afvist: intet identificerbart signal"


def test_classify_se_naermere_when_dimensions_found():
    listing = {"attributes": {"width_cm": 89.0, "height_cm": 209.0}}
    result = classify(listing, {})
    assert result["vurdering"] == "se nærmere"
    assert result["score"] == 2
    assert len(result["spoergsmaal_til_saelger"]) > 0


def test_fire_rating_requires_door_window_context():
    """P3 (Opus-review af 935 live DBA-titler, 2026-10-05): uden et dør-/
    vindues-/glas-/karm-ord matchede _FIRE_CLASS_PATTERN også andre
    produkters EGNE typenumre -- 3 MÅLTE falske positiver, verbatim fra
    research."""
    assert extract_fire_rating("Blu-ray afspiller, Panasonic, BMP-BD30") is None
    assert extract_fire_rating("Wacker BS60-4 Jordloppe") is None
    assert extract_fire_rating("Jordloppe Wacker BS60-2i") is None
    # Ægte fund skal stadig virke -- konteksten ("dør") er til stede.
    assert extract_fire_rating("Stål branddør EI60 mål 90 x 210 cm") == "EI60"
    assert extract_fire_rating("Stålbranddør EI60") == "EI60"


def test_karmsaet_alone_is_an_accessory_not_a_whole_door():
    """P11: 'Swedoor karmsæt tung 128 mm 8x21' blev vist som en hel dør
    (modulmål-grenen læste '8x21' som 80x210cm), men et karmsæt er løst
    tilbehør uden dørblad. Verbatim fra research, 2026-10-05."""
    assert is_accessory_title("Swedoor karmsæt tung 128 mm 8x21")
    # Et karmsæt der sælges MED en hel dør skal stadig IKKE afvises (samme
    # R11-mønster som øvrige _ACCESSORY_WORD-ord).
    assert not is_accessory_title("Hvid yderdør 91x216 cm med karmsæt")


def test_classify_scores_a_single_known_dimension_too():
    """P10: gren 4 i doere_normalize.py (ét mål, intet brandklasse-tal) gav
    hidtil altid 0 point her, fordi classify() krævede BÅDE bredde og
    højde -- dermed reelt død kode. Nu +1 for ét mål alene. To MÅLTE reelle
    tab: 'Sweedoor Hvid indvendig dør 203 cm' og 'Hvid terrassedør h 210,8
    cm.' endte begge som afvis uden denne rettelse."""
    listing = {"attributes": {"height_cm": 203.0}}
    result = classify(listing, {})
    assert result["vurdering"] == "se nærmere"
    assert result["score"] == 1


def test_classify_scores_explicit_brand_word_even_without_a_number():
    """P2 (samme review): 19% af alt med eksplicit brand-ordforråd (31 af
    159 titler) blev afvist, fordi selve ordet 'branddør'/'brandvindue'
    vejede intet uden et numerisk klassetal. 28 af de 31 var ægte
    branddøre/-vinduer uden tal i titlen -- to verbatim eksempler herunder."""
    listing = {"attributes": {}, "title": "Branddøre af mærket Safco Doors"}
    result = classify(listing, {})
    assert result["vurdering"] == "se nærmere"
    assert result["score"] == 1

    listing2 = {"attributes": {}, "title": "Helt nye brandvinduer"}
    result2 = classify(listing2, {})
    assert result2["vurdering"] == "se nærmere"

    # Uden et brandord OG uden mål/klasse skal afvis stadig stå fast.
    listing3 = {"attributes": {}, "title": "Et helt almindeligt bord"}
    assert classify(listing3, {})["vurdering"] == "afvis"


def test_classify_scores_fire_rating_and_thickness_too():
    listing = {
        "attributes": {
            "width_cm": 89.0,
            "height_cm": 209.0,
            "thickness_cm": 6.4,
            "fire_rating": "BD60",
        }
    }
    result = classify(listing, {})
    assert result["vurdering"] == "se nærmere"
    assert result["score"] == 5  # 2 (mål) + 2 (brandklasse) + 1 (tykkelse)
    assert result["mangler_info"] == []
