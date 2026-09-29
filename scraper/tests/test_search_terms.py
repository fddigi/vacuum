"""Test af de kildespecifikke søgeord-supplementer (ny 2026-09-29,
Opus-review af intake). Mekanikken er bevidst bygget så INGEN kilde-fil skal
ændres: alle otte sources/*.py læser allerede `primary + secondary`, så et
supplement kan lægges i `secondary` for netop den ene kilde."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.search_terms import config_for_source

BASE = {
    "search_terms": {
        "primary": ["asbestsuger", "industristøvsuger"],
        "secondary": ["Nilfisk Attix 33-2H"],
        "per_source": {"klaravik": ["støvsuger"], "auktionshuset": ["støvsuger"]},
    },
    "playwright": {"headless": True},
}


def _terms(config):
    return config["search_terms"]["primary"] + config["search_terms"].get("secondary", [])


def test_source_without_a_supplement_is_untouched():
    """dba/blocket/kleinanzeigen fungerer allerede med de specifikke
    modelfraser -- et bart 'støvsuger'/'Nilfisk' ville live-målt koste ~50
    irrelevante annoncer pr. term af playwright.max_pages_total."""
    for name in ("dba", "blocket", "kleinanzeigen", "retrade"):
        assert config_for_source(BASE, name) is BASE, name


def test_supplement_is_added_not_substituted():
    """Regression: supplementet må ALDRIG erstatte secondary. I Turso-tilstand
    er secondary tom (main.py flader alt ud i primary), men i lokal-only-
    tilstand indeholder den config.yaml's ~57 modelfraser."""
    config = config_for_source(BASE, "klaravik")
    terms = _terms(config)
    assert "Nilfisk Attix 33-2H" in terms
    assert "støvsuger" in terms
    assert terms.count("støvsuger") == 1
    # Originalen må ikke muteres -- den genbruges til de øvrige kilder.
    assert BASE["search_terms"]["secondary"] == ["Nilfisk Attix 33-2H"]


def test_supplement_is_not_duplicated_if_already_present():
    base = {
        **BASE,
        "search_terms": {**BASE["search_terms"], "secondary": ["støvsuger"]},
    }
    assert _terms(config_for_source(base, "klaravik")).count("støvsuger") == 1


def test_missing_per_source_key_is_harmless():
    base = {"search_terms": {"primary": ["asbestsuger"], "secondary": []}}
    assert config_for_source(base, "klaravik") is base
