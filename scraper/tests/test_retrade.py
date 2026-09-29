"""Regressionstest for retrade.py's _parse_price() -- se kildens egen
docstring for den fulde begrundelse (Opus-review, 2026-09-29): Retrade viser
hver auktion i sælgerens egen valuta (DKK/SEK/NOK), ikke kun DKK."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.retrade import _CURRENCY_TO_COUNTRY, _parse_price


def test_parses_dkk_sek_and_nok():
    assert _parse_price("2.100 DKK") == (2100.0, "DKK")
    assert _parse_price("10.000 NOK") == (10000.0, "NOK")
    assert _parse_price("1.500 SEK") == (1500.0, "SEK")


def test_zero_bid_is_not_a_real_price():
    """'0 DKK'/'0 NOK' betyder 'intet bud endnu', ikke en reel pris."""
    assert _parse_price("0 DKK") is None
    assert _parse_price("0 NOK") is None


def test_unrecognized_currency_returns_none_not_a_crash():
    assert _parse_price("100 EUR") is None
    assert _parse_price("") is None
    assert _parse_price(None) is None


def test_currency_to_country_mapping_matches_import_costs_eu_list():
    """NO er bevidst UDENFOR config.yaml's import_costs.eu_country_codes, så
    en norsk lot korrekt får import-/toldberegning i normalize.py."""
    assert _CURRENCY_TO_COUNTRY == {"DKK": "DK", "SEK": "SE", "NOK": "NO"}
