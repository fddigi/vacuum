"""Regressionstest for kleinanzeigen.py's solgt-verifikation -- se
verify_sold_status()'s docstring for det MÅLTE fund bag <h1>-mønsteret
(25 rigtige, gemte kleinanzeigen-URL'er genbesøgt live 2026-10-05: 7
"Gelöscht", 2 "Reserviert", 16 uden præfiks/stadig aktive)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.kleinanzeigen import _SOLD_H1_PREFIX_PATTERN


def test_matches_real_deleted_and_reserved_h1_texts():
    assert _SOLD_H1_PREFIX_PATTERN.match(
        "Gelöscht • Kärcher Nass /Trockensauger Professinal NT 35/1 Tact Te"
    )
    assert _SOLD_H1_PREFIX_PATTERN.match(
        "Reserviert • Staubsauger Kärcher Nass Trockensauger NT 35/1 Tact Te H"
    )


def test_does_not_match_a_normal_active_listing_title():
    """Verbatim fra en stadig-aktiv annonce (samme live-test)."""
    assert not _SOLD_H1_PREFIX_PATTERN.match(
        "Kärcher Nass- und Trockensauger NT 30/1 Tact Te M 30 Liter #NEU"
    )


def test_does_not_false_positive_on_a_title_that_merely_contains_the_word():
    """'Gelöscht'/'Reserviert' et sted MIDT i en titel er ikke et statusmærke
    -- kun et PRÆFIKS efterfulgt af '•' tæller (se modulets docstring)."""
    assert not _SOLD_H1_PREFIX_PATTERN.match("Staubsauger reserviert für Max, bitte nicht kaufen")
    assert not _SOLD_H1_PREFIX_PATTERN.match("NT 35/1 - wurde bereits gelöscht laut Verkäufer")
