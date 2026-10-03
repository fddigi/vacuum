"""Regressionstest for categories.py's registry -- se modulets docstring for
hvorfor dette dispatch-lag findes (multi-kategori SHV-sourcing, 2026-10-03)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper import classify, normalize
from scraper.categories import CATEGORIES, DEFAULT_CATEGORY


def test_stoevsugere_category_wraps_existing_vacuum_functions_unchanged():
    """Kategori-generaliseringen skal være en rent additiv omlægning --
    stoevsugere-kategorien peger på PRÆCIS de samme funktioner som før
    refaktoreringen, ingen ny logik indsat imellem."""
    category = CATEGORIES["stoevsugere"]
    assert category is DEFAULT_CATEGORY
    assert category.normalize_listing is normalize.normalize_listing
    assert category.classify is classify.classify
    assert category.is_accessory_or_rental is normalize.is_accessory_or_rental
    assert category.is_accessory_title is normalize.is_accessory_title
    assert category.seller_questions == classify.SELLER_QUESTIONS


def test_every_category_implements_the_full_contract():
    """Enhver fremtidig kategori SKAL udfylde alle felter -- en manglende
    funktion ville først fejle ved kørsel (AttributeError i pipeline.py),
    ikke ved import. Denne test fanger det tidligere, for ALLE registrerede
    kategorier, ikke kun stoevsugere."""
    for key, category in CATEGORIES.items():
        assert category.key == key
        assert callable(category.normalize_listing)
        assert callable(category.classify)
        assert callable(category.is_accessory_or_rental)
        assert callable(category.is_accessory_title)
        assert isinstance(category.seller_questions, list)
        assert len(category.seller_questions) > 0
