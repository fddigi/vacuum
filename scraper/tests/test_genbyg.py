"""Regressionstest for genbyg.py's prisparsing, specs-udtræk og kort-parsing
-- se kildens egen docstring for den danske tusind-/decimalnotation
("1.500,00" = 1500 kr., ikke 1,5) og for struktureret vs. fritekst-mål."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.genbyg import _danish_decimal_to_float, _parse_listing_cards, _parse_specs

_CARD_PATH = (
    "/doere-vinduer/brugte-doere/branddoere/bd60-branddoere/274794/bd60-branddoer-uden-karm"
)
REAL_CARD_HTML = f"""
<div class="grid__item product-list__item" data-product-url="{_CARD_PATH}">
  <div class="product-list__item__info">
    <div>
      <h2 class="product-list__item__name">BD60 branddør uden karm</h2>
      <span class="product-list__item__id">
  Varenr.:  274794  </span>
      <ul class="product-list__item__specs">
      <li class="product-list__item__specs__item">Bredde: 92,70 cm</li>
        <li class="product-list__item__specs__item">Højde: 205,50 cm</li>
        <li class="product-list__item__specs__item">Tykkelse: 6,40 cm</li>
  </ul>
    </div>
    <div>
      <div class="product-list__item__price">
    <span class="product-list__item__price__current">
        1.500,00    pr.stk  </span>
</div>
    </div>
  </div>
</div>
"""


def test_danish_decimal_notation_period_is_thousands_comma_is_decimal():
    assert _danish_decimal_to_float("1.500,00") == 1500.0
    assert _danish_decimal_to_float("92,70") == 92.7
    assert _danish_decimal_to_float("not a number") is None


def test_parse_specs_extracts_width_height_thickness_in_cm():
    specs_text = "Bredde: 92,70 cm</li>Højde: 205,50 cm</li>Tykkelse: 6,40 cm"
    assert _parse_specs(specs_text) == {
        "width_cm": 92.7,
        "height_cm": 205.5,
        "thickness_cm": 6.4,
    }


def test_parse_specs_handles_missing_fields_gracefully():
    assert _parse_specs("Bredde: 102,50 cm") == {"width_cm": 102.5}
    assert _parse_specs("") == {}
    assert _parse_specs(None) == {}


def test_parse_listing_cards_against_real_card_markup():
    """REAL_CARD_HTML er verbatim uddrag fra genbyg.dk (2026-10-04, varenr.
    274794) -- se genbyg.py's docstring for den fulde research."""
    cards = _parse_listing_cards(REAL_CARD_HTML)
    assert len(cards) == 1
    card = cards[0]
    assert card["title"] == "BD60 branddør uden karm"
    assert card["varenr"] == "274794"
    assert card["url"] == "https://genbyg.dk" + _CARD_PATH
    specs = _parse_specs(card["specs_text"])
    assert specs == {"width_cm": 92.7, "height_cm": 205.5, "thickness_cm": 6.4}
