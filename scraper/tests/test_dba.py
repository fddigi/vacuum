"""Regressionstest for sources/dba.py's thumbnail-parser (_parse_image_url) og
prisparser -- se kildens egen kommentar over _IMAGE_SELECTORS for de målte
DOM-varianter.

Alle billed-testcases bygger på attributter observeret LIVE mod dba.dk
2026-10-03 på 537 rigtige dør-/vinduesannoncer (10 søgeord). Kortene har præcis
to varianter: en karrusel med flere <img> (401/537, hvor det synlige bærer
"--active") og et enkelt <img> uden karrusel-klasser (133/537). 3 af 537 kort
havde slet intet <img>.

Fake-objekterne følger samme mønster som test_facebook.py's FakePage: kildens
parser rører kun query_selector/get_attribute, så den kan testes uden en
kørende browser.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.dba import (
    _first_srcset_url,
    _parse_image_url,
    _parse_listing_cards,
    _parse_price,
)

CDN = "https://images.dbastatic.dk"


class FakeElement:
    def __init__(self, text="", **attrs):
        self._text = text
        self._attrs = attrs

    def get_attribute(self, name):
        return self._attrs.get(name.replace("-", "_"))

    def inner_text(self):
        return self._text


class FakeCard:
    """Svarer på query_selector ud fra en selector->element-tabel, og
    returnerer None for alt andet (som Playwright gør)."""

    def __init__(self, elements, text=""):
        self._elements = elements
        self._text = text

    def query_selector(self, selector):
        return self._elements.get(selector)

    def query_selector_all(self, selector):
        el = self._elements.get(selector)
        return [el] if el else []

    def inner_text(self):
        return self._text


class FakePage:
    def __init__(self, cards):
        self._cards = cards

    def query_selector_all(self, selector):
        return self._cards if selector == "article.sf-search-ad" else []


# ---------------------------------------------------------------------------
# _parse_image_url
# ---------------------------------------------------------------------------


def test_carousel_card_uses_the_active_image_not_just_any_image():
    """Flerbilled-varianten har ALLE karrusel-billeder i DOM'et samtidig. Kun
    det synlige (--active) er annoncens thumbnail, og det skal vælges via sin
    egen klasse -- ikke via "første <img> i kortet", som blot tilfældigvis er
    det samme i dag."""
    active = f"{CDN}/dynamic/default/item/14998089/5c691970-ebdd-4d9d-af0c-6b2d194fe8ec"
    other = f"{CDN}/dynamic/default/item/14998089/c5be9be7-72d8-4531-a62f-2c982a790290"
    card = FakeCard(
        {
            "img.sf-ad-carousel-desktop-item--active": FakeElement(src=active),
            "img": FakeElement(src=other),
        }
    )
    assert _parse_image_url(card) == active


def test_single_image_card_falls_back_to_the_plain_img():
    """Enkeltbilled-varianten (133/537 kort) har ingen karrusel-klasse."""
    src = f"{CDN}/dynamic/480w/item/23661633/f9f29754-746b-47a1-93f1-ec988695b96f"
    card = FakeCard({"img": FakeElement(src=src, loading="lazy")})
    assert _parse_image_url(card) == src


def test_lazy_loading_attribute_does_not_block_the_src():
    """loading="lazy" er kun et browser-HENT-hint; src står i den
    serverrenderede HTML. Målt uden scroll: 54/54 kort havde src. Testen
    fastholder at parseren ikke indfører et krav om scroll-triggering."""
    src = f"{CDN}/dynamic/480w/item/21119563/716d3d10-aec5-4967-a5e7-66ced27abb85"
    card = FakeCard({"img": FakeElement(src=src, loading="lazy", data_src=None, srcset=None)})
    assert _parse_image_url(card) == src


def test_card_without_any_image_returns_none_not_a_crash():
    """3 af 537 rigtige kort havde intet <img> (annonce uden uploadet
    billede). Feltet er nullable, og kortet må ikke droppes."""
    assert _parse_image_url(FakeCard({})) is None


def test_srcset_is_used_only_when_src_is_missing():
    srcset = (
        f"{CDN}/dynamic/240w/38/383ff3ef 240w, "
        f"{CDN}/dynamic/320w/38/383ff3ef 320w, "
        f"{CDN}/dynamic/480w/38/383ff3ef 480w"
    )
    card = FakeCard({"img": FakeElement(src=None, srcset=srcset)})
    assert _parse_image_url(card) == f"{CDN}/dynamic/240w/38/383ff3ef"


def test_data_src_is_used_when_src_is_missing():
    src = f"{CDN}/dynamic/480w/item/1/abc"
    card = FakeCard({"img": FakeElement(src=None, data_src=src)})
    assert _parse_image_url(card) == src


def test_non_absolute_and_data_uri_sources_are_rejected():
    """En data:-placeholder (den klassiske lazy-load-teknik) må aldrig gemmes
    som et billede, og et relativt src er ikke brugbart i frontend'en."""
    assert (
        _parse_image_url(FakeCard({"img": FakeElement(src="data:image/gif;base64,R0lGOD")})) is None
    )
    assert _parse_image_url(FakeCard({"img": FakeElement(src="/relativ/sti.jpg")})) is None
    assert _parse_image_url(FakeCard({"img": FakeElement(src="")})) is None


def test_first_srcset_url_handles_empty_and_malformed_input():
    assert _first_srcset_url(None) is None
    assert _first_srcset_url("") is None
    assert _first_srcset_url("240w, 320w") is None
    assert _first_srcset_url(f"{CDN}/a") == f"{CDN}/a"


# ---------------------------------------------------------------------------
# _parse_listing_cards -- at billedet faktisk føres med ud af kort-parseren
# ---------------------------------------------------------------------------


def test_listing_card_carries_the_image_url_through():
    src = f"{CDN}/dynamic/default/item/25188708/abc"
    card = FakeCard(
        {
            "h2": FakeElement("Branddør BD60 mål 89 x 209 cm"),
            "a.sf-search-ad-link": FakeElement(href="https://www.dba.dk/recommerce/forsale/item/1"),
            ".font-bold": FakeElement("1.500 kr."),
            "img.sf-ad-carousel-desktop-item--active": FakeElement(src=src),
        }
    )
    (result,) = _parse_listing_cards(FakePage([card]))
    assert result == {
        "title": "Branddør BD60 mål 89 x 209 cm",
        "price_text": "1.500 kr.",
        "url": "https://www.dba.dk/recommerce/forsale/item/1",
        "image_url": src,
    }


def test_listing_card_without_image_still_yields_the_listing():
    card = FakeCard(
        {
            "h2": FakeElement("Branddør BD30"),
            "a.sf-search-ad-link": FakeElement(href="https://www.dba.dk/recommerce/forsale/item/2"),
            ".font-bold": FakeElement("900 kr."),
        }
    )
    (result,) = _parse_listing_cards(FakePage([card]))
    assert result["image_url"] is None
    assert result["title"] == "Branddør BD30"


# ---------------------------------------------------------------------------
# _parse_price (ingen tidligere dækning)
# ---------------------------------------------------------------------------


def test_parse_price_handles_danish_thousand_separators_and_nbsp():
    assert _parse_price("2.500\xa0kr.") == (2500.0, "DKK")
    assert _parse_price("14.200 kr.") == (14200.0, "DKK")
    assert _parse_price("400 kr") == (400.0, "DKK")


def test_parse_price_returns_none_amount_when_no_price_is_shown():
    assert _parse_price("Gratis") == (None, "DKK")
    assert _parse_price("") == (None, "DKK")
    assert _parse_price(None) == (None, "DKK")
