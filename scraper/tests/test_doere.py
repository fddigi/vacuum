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
