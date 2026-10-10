"""Regressionstest for skave_nedbrydning.py's kort-/mål-udtræk -- se modulets
docstring for de målte fund (strukturerede b/h/km/v-felter, 30s obligatorisk
crawl-delay pr. robots.txt)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.skave_nedbrydning import (
    _CATEGORY_SLUGS,
    _danish_decimal_to_float,
    _parse_cards,
    _parse_infos,
)

# Verbatim card-fragment fra en rigtig side (vinduer, produkt 405), 2026-10-10.
_REAL_CARD_HTML = """
<div class="product-grid  col-sm-6 col-md-4 col-lg-3  px-2 mb-3 ">
    <div class="product-thumb flex-column row no-gutters justify-content-between">
        <div class="image mb-2">
            <a href="https://www.skave-nedbrydning.dk/vareliste/vinduer/fartkarmsvindue-405">
                <img src="x.jpg" alt="Fastkarmsvindue" class="img-fluid">
            </a>
        </div>
        <div class="caption px-3 flex-grow-1">
            <div class="name">Fastkarmsvindue</div>
            <div class="description">
                2-lag termo, står i bunden af rk N - passer til id 6450.
            </div>
        </div>
        <div class="price px-3 row no-gutters justify-content-center align-items-center">
            <div class="infos col-12 mt-3">
                <strong>km</strong>: 14,0 cm<br />
                <strong>b</strong>: 285,0 cm<br />
                <strong>h</strong>: 125,0 cm<br />
                <strong>v</strong>: 122,0 kg<br />
                <strong>Produkt ID:</strong> 405<br />
                <strong>Antal på lager:</strong> 3
            </div>
            <div class="col-12">
                1.000,00<span class="currency-symbol"> kr. pr. stk.</span>
            </div>
        </div>
    </div>
</div>
"""


def test_danish_decimal_notation():
    assert _danish_decimal_to_float("1.000,00") == 1000.0
    assert _danish_decimal_to_float("285,0") == 285.0
    assert _danish_decimal_to_float("ugyldig") is None


def test_parse_cards_verbatim_real_card():
    cards = _parse_cards(_REAL_CARD_HTML)
    assert len(cards) == 1
    card = cards[0]
    assert card["title"] == "Fastkarmsvindue"
    assert card["price"] == 1000.0
    assert card["url"] == "https://www.skave-nedbrydning.dk/vareliste/vinduer/fartkarmsvindue-405"
    assert "2-lag termo" in card["description"]


def test_parse_infos_extracts_width_height_and_thickness_as_karmdybde():
    attrs = _parse_infos(
        "<strong>km</strong>: 14,0 cm<br /><strong>b</strong>: 285,0 cm<br />"
        "<strong>h</strong>: 125,0 cm<br /><strong>v</strong>: 122,0 kg<br />"
    )
    assert attrs == {"thickness_cm": 14.0, "width_cm": 285.0, "height_cm": 125.0}


def test_parse_cards_handles_card_with_no_description():
    html = _REAL_CARD_HTML.replace(
        '<div class="description">\n                2-lag termo, står i bunden af rk N - '
        "passer til id 6450.\n            </div>",
        "",
    )
    cards = _parse_cards(html)
    assert len(cards) == 1
    assert cards[0]["description"] == ""


def test_parse_cards_returns_empty_list_for_no_matches():
    assert _parse_cards("<html><body>ingen produkter</body></html>") == []


def test_category_slugs_map_to_valid_subtype_hints():
    """Hver kategori skal pege på en af de fire subtype-bøtter
    doere_normalize.classify_subtype() forstår."""
    valid_hints = {"vindue", "terrassedoer", "doer_andet"}
    assert set(_CATEGORY_SLUGS.values()) <= valid_hints
    assert "vinduer" in _CATEGORY_SLUGS
    assert _CATEGORY_SLUGS["terrassedore"] == "terrassedoer"
    assert _CATEGORY_SLUGS["dore-udvendige"] == "doer_andet"
