"""Regressionstest for jyskauktion.py's prisparsing, katalog-ID-udtræk og
thumbnail-parser -- se kildens egen docstring for hvorfor denne kilde
gennembladrer i stedet for at søge (ingen fungerende tekstsøgning fundet på
sitet, 2026-10-03/04), og for hvorfor thumbnailet (tilføjet 2026-10-05) er
den eneste praktiske afhjælpning for annoncer hvor ALT identificerbart kun
findes i billedet, fx "STØVSUGER." uden mærke/model i selve teksten."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.jyskauktion import _CATALOG_ID_PATTERN, _parse_image_url, _parse_price


class FakeElement:
    def __init__(self, **attrs):
        self._attrs = attrs

    def get_attribute(self, name):
        return self._attrs.get(name)


class FakeCard:
    def __init__(self, img=None):
        self._img = img

    def query_selector(self, selector):
        return self._img if selector == "img" else None


def test_parses_dkk_bid_ignoring_eur():
    """.productBid viser altid DKK OG EUR på to linjer -- kun DKK bruges."""
    assert _parse_price("50 DKK\n6,78 EUR") == 50.0
    assert _parse_price("1.234 DKK\n167,86 EUR") == 1234.0


def test_zero_bid_is_not_a_real_price():
    """'0 DKK' betyder 'intet bud endnu', ikke en reel pris -- samme fund
    som retrade.py/auktionshuset.py's tilsvarende auktionskilder."""
    assert _parse_price("0 DKK\n0 EUR") is None


def test_unparseable_price_returns_none_not_a_crash():
    assert _parse_price("") is None
    assert _parse_price(None) is None
    assert _parse_price("Intet bud endnu") is None


def test_catalog_id_extracted_from_homepage_link():
    m = _CATALOG_ID_PATTERN.search("/catalog/313")
    assert m.group(1) == "313"
    m2 = _CATALOG_ID_PATTERN.search("/catalog/313/4/")
    assert m2.group(1) == "313"


def test_parse_image_url_makes_relative_src_absolute():
    """Verbatim fra et rigtigt kort (produkt 74542, 2026-10-05):
    src="/upload/eed4e9ad619b9a22be92ddf29347bd6e.jpg"."""
    card = FakeCard(img=FakeElement(src="/upload/eed4e9ad619b9a22be92ddf29347bd6e.jpg"))
    assert (
        _parse_image_url(card)
        == "https://www.jyskauktion.dk/upload/eed4e9ad619b9a22be92ddf29347bd6e.jpg"
    )


def test_parse_image_url_handles_missing_image_gracefully():
    assert _parse_image_url(FakeCard(img=None)) is None
    assert _parse_image_url(FakeCard(img=FakeElement(src=""))) is None
