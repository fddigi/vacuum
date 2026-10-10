"""Regressionstest for jk_genbrugscenter.py's mål-udtræk og kategori->subtype-
mapping -- se modulets docstring for de målte fund bag kategori-ID'erne
(verificeret live mod jk-genbrugscenter.dk's WooCommerce Store API,
2026-10-10)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.jk_genbrugscenter import (
    _ACCESSORY_CATEGORY_ID,
    _clean_title,
    _parse_dimensions,
    _strip_html,
    _subtype_hint_for,
)


def test_parse_dimensions_verbatim_from_real_short_description():
    """Verbatim fra et rigtigt produkt (Stålbranddør EL60, varenr. OB676)."""
    html = "<p><strong>Bredde 108</strong></p>\n<p><strong>Højde 217</strong></p>"
    assert _parse_dimensions(html) == {"width_cm": 108.0, "height_cm": 217.0}


def test_parse_dimensions_handles_decimal_comma():
    html = "<p><strong>Bredde 95,5</strong></p><p><strong>Højde 239,5</strong></p>"
    assert _parse_dimensions(html) == {"width_cm": 95.5, "height_cm": 239.5}


def test_parse_dimensions_handles_period_separator_without_misreading_it_as_a_decimal():
    """REGRESSION (2026-10-10): en tidligere version brugte en lazy
    `[^\\d]*?`-separator FØR talgruppen `[\\d.,]+` -- men talgruppen optager
    selv punktum, så separatoren kunne under-matche og lade "." fra
    "Bredde. 59" blive fanget som SELVE tallet (`float(".")` -> ValueError,
    stille 0-resultat). 23 af 73 Branddøre-varer havde netop dette
    "Bredde. N"-format (manuel indtastning, ikke "Bredde N"). Verbatim fra et
    rigtigt produkt (Stålbranddør EI60)."""
    html = "<p><strong>Bredde. 60</strong></p>\n<p><strong>Højde. 209</strong></p>"
    assert _parse_dimensions(html) == {"width_cm": 60.0, "height_cm": 209.0}


def test_parse_dimensions_period_separator_with_decimal_value():
    """Samme separator-bug, men med en decimalværdi -- skal stadig læse
    "85,5" korrekt og ikke forveksle separator-punktummet med tallets eget."""
    html = "<p><strong>Bredde. 85,5</strong></p><p><strong>Højde. 201,5</strong></p>"
    assert _parse_dimensions(html) == {"width_cm": 85.5, "height_cm": 201.5}


def test_parse_dimensions_missing_returns_empty_dict():
    assert _parse_dimensions("<p>Ingen mål oplyst</p>") == {}
    assert _parse_dimensions("") == {}
    assert _parse_dimensions(None) == {}


def test_strip_html_removes_tags_keeps_text():
    assert _strip_html("<p><strong>Bredde 108</strong></p>") == "Bredde 108"


def test_clean_title_unescapes_html_entities():
    """Store API'ets 'name'-felt er entity-encodet, ikke ren tekst -- MÅLT
    fund: "Ståldør &#8211; Novoferm" i stedet for "Ståldør – Novoferm"."""
    assert _clean_title("Ståldør &#8211; Novoferm") == "Ståldør – Novoferm"
    assert _clean_title("94&#215;160 cm") == "94×160 cm"
    assert _clean_title("Brand &amp; lyddør BD60") == "Brand & lyddør BD60"


def test_subtype_hint_branddoer_wins_over_generic_door_category():
    """En branddør ligger altid OGSÅ i den generiske 'Nye og brugte døre'
    (207) -- det mere specifikke branddør-ID skal vinde."""
    assert _subtype_hint_for({210, 207}) == "branddoer"


def test_subtype_hint_terrassedoer():
    assert _subtype_hint_for({208, 207}) == "terrassedoer"


def test_subtype_hint_vindue_from_any_leaf_category():
    assert _subtype_hint_for({339, 340, 205}) == "vindue"  # Fastkarmsvindue + Vinduesparti


def test_subtype_hint_generic_door_category():
    assert _subtype_hint_for({219, 207}) == "doer_andet"  # Indvendigedøre


def test_subtype_hint_none_for_irrelevant_category():
    """Tømmer/radiator/tagsten osv. -- helt uden for scope, se modulets
    docstring for de ~270 varer dette filtrerer væk."""
    assert _subtype_hint_for({211}) is None  # Tømmer og profilbrædder
    assert _subtype_hint_for({643}) is None  # Radiator
    assert _subtype_hint_for(set()) is None


def test_accessory_category_id_is_excluded_upstream():
    """fetch() springer denne kategori over FØR subtype-hintet overhovedet
    beregnes -- dette er blot en dokumentations-regressionstest for selve
    ID-konstanten, så en fremtidig omdøbning i koden bliver fanget."""
    assert _ACCESSORY_CATEGORY_ID == 218
