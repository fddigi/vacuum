"""Regressionstest for sources/facebook.py's aria-label-parser -- se kildens
egen docstring for hvorfor aria-label bruges i stedet for CSS-selectors
(Facebooks klasser er fuldstændig obfuskerede og ustabile). Alle testcases er
verbatim aria-labels observeret live 2026-09-30 mod en rigtig, logget-ind
session."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.facebook import _looks_like_session_invalid, _parse_card, _parse_price


def test_parses_simple_card():
    result = _parse_card("Industristøvsuger, 600 kr, Kalundborg, opslag 1153112620724561")
    assert result == {
        "title": "Industristøvsuger",
        "price_amount": 600.0,
        "url": "https://www.facebook.com/marketplace/item/1153112620724561/",
        "location": "Kalundborg",
    }


def test_parses_card_with_reduced_price():
    """'reduceret fra'-klausulen (nedsat pris) skal springes helt over --
    kun den AKTUELLE pris (første tal) skal bruges."""
    result = _parse_card(
        "Starmix industristøvsuger – M-klasse, 2700 kr, reduceret fra 3000 kr, Sorø, "
        "opslag 988309764283296"
    )
    assert result["price_amount"] == 2700.0
    assert result["title"] == "Starmix industristøvsuger – M-klasse"
    assert result["location"] == "Sorø"


def test_parses_card_with_multi_comma_location():
    """Lokationer som 'By, Region, Denmark' indeholder selv kommaer -- et
    naivt split(',') ville fejle her. Regex'en ankrer i stedet på de to
    entydige dele (pris-tal og 'opslag <id>')."""
    result = _parse_card(
        "Nilfisk alto attix 360-11, 1500 kr, Strøby Egede, Roskilde, Denmark, "
        "opslag 28422914250703941"
    )
    assert result["title"] == "Nilfisk alto attix 360-11"
    assert result["location"] == "Strøby Egede, Roskilde, Denmark"
    assert result["price_amount"] == 1500.0


def test_parses_card_with_multiline_title():
    """Titler kan indeholde linjeskift i selve DOM'et -- skal normaliseres
    til enkelte mellemrum, ikke tabt eller efterladt som \\n i output."""
    aria_label = (
        "Nilfisk støvsugerposer. 5 stk. ATTIX 33 H. \nATTIX 44 44 H\n"
        "VHS 40 HC, VHS 42 HC., 800 kr, Roskilde, Denmark, opslag 1342334914680681"
    )
    result = _parse_card(aria_label)
    assert "\n" not in result["title"]
    assert result["price_amount"] == 800.0


def test_thousand_separator_price_parses_correctly():
    assert _parse_price("1.234.567") == 1234567.0


def test_unparseable_aria_label_returns_none():
    assert _parse_card("") is None
    assert _parse_card(None) is None
    assert _parse_card("Helt uforståelig tekst uden struktur") is None


def test_session_invalid_detection():
    class FakePage:
        def __init__(self, text):
            self._text = text

        def inner_text(self, _selector):
            return self._text

    assert _looks_like_session_invalid(
        FakePage("Du skal træffe et valg om Marketplace\nKom i gang")
    )
    assert _looks_like_session_invalid(FakePage("Log på Facebook\nE-mail eller telefonnummer"))
    assert not _looks_like_session_invalid(
        FakePage("Industristøvsuger, 600 kr, Kalundborg, opslag 123")
    )
