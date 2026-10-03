"""Regressionstest for jyskauktion.py's prisparsing og katalog-ID-udtræk --
se kildens egen docstring for hvorfor denne kilde gennembladrer i stedet for
at søge (ingen fungerende tekstsøgning fundet på sitet, 2026-10-03/04)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.jyskauktion import _CATALOG_ID_PATTERN, _parse_price


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
