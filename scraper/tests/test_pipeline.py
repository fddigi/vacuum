"""Regressionstest for pipeline.py's tilbehørs-override (se pipeline.py's R12-
kommentar). Kører run_source() mod en in-memory LocalStore med én enkelt fake
fetch(), for at bekræfte at en tilbehørsannonce der NÆVNER en whitelistet
model ikke lækker model_key/dust_class/klasse_kilde ind i den lagrede række
(hvilket ville få Workerens "valideret"-felt til fejlagtigt at blive true)."""

from __future__ import annotations

import json

from scraper_core.local_db import LocalStore

from scraper.pipeline import run_source

CONFIG = {
    "currency": {"eur_dkk": 7.46, "sek_dkk": 0.70, "usd_dkk": 6.90},
    "filter_replacement_estimate_dkk": 800,
    "prislofter": {
        "kompakt_h": {"koeb_max": 3500, "god_handel_max": 2500},
        "stor_h": {"koeb_max": 5000, "god_handel_max": 3500},
        "m_klasse": {"koeb_max": 2000, "god_handel_max": 1200},
    },
}


def _fake_fetch(config, dry_run=False):
    return [
        {
            "title": "Sicherheitsfiltersack für Attix 30-0H PC, 5er Pack",
            "description": "",
            "price_amount": 1111.54,
            "price_currency": "DKK",
            "url": "https://example.test/1",
            "extra": {},
        }
    ]


def test_accessory_override_clears_model_and_class_fields_too():
    """Regression -- R12: uden dette blev en tilbehørsannonce der nævner en
    kompatibel model gemt med et ægte model_key/dust_class='H'/
    klasse_kilde='modelnavn', selvom vurdering korrekt blev sat til 'afvis'.
    Workerens 'valideret'-felt kigger UDELUKKENDE på model_key/klasse_kilde/
    dust_class, ikke på vurdering, og ville derfor stadig vise annoncen som
    "✓ valideret" i frontend'en."""
    with LocalStore(":memory:") as store:
        raw_count, changed, _ = run_source(store, "kleinanzeigen", _fake_fetch, CONFIG)
        assert raw_count == 1
        assert changed == 1

        row = store.connection.execute(
            "SELECT vurdering, model_key, dust_class, klasse_kilde, mangler_info FROM listings"
        ).fetchone()

    assert row["vurdering"] == "afvis"
    assert row["model_key"] is None
    assert row["dust_class"] == "ingen (L/ukendt)"
    assert row["klasse_kilde"] is None
    assert "tilbehør" in json.loads(row["mangler_info"])[0]


def _fetch_factory(urls):
    def _fetch(config, dry_run=False):
        return [
            {
                "title": f"Kärcher NT {i}",
                "description": "",
                "price_amount": 1000.0 + i,
                "price_currency": "DKK",
                "url": url,
                "extra": {},
            }
            for i, url in enumerate(urls)
        ]

    return _fetch


def test_misses_increments_only_for_items_absent_from_a_run_that_found_something():
    """Solgt-detektion (2026-10-05, ported fra seng/PASPEAKERS): en annonce
    der ikke dukker op i en kørsel hvor kilden ELLERS fandt noget, skal få
    misses talt op -- men en annonce der STADIG findes skal forblive på 0."""
    with LocalStore(":memory:") as store:
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a", "https://b"]), CONFIG)
        # Næste kørsel finder kun "a" igen -- "b" er forsvundet.
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a"]), CONFIG)

        rows = {
            row["url"]: row["misses"]
            for row in store.connection.execute("SELECT url, misses FROM listings")
        }
    assert rows["https://a"] == 0
    assert rows["https://b"] == 1


def test_misses_resets_to_zero_when_item_reappears():
    with LocalStore(":memory:") as store:
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a", "https://b"]), CONFIG)
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a"]), CONFIG)
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a", "https://b"]), CONFIG)

        row = store.connection.execute(
            "SELECT misses FROM listings WHERE url = 'https://b'"
        ).fetchone()
    assert row["misses"] == 0


def test_zero_result_run_does_not_increment_misses_for_anyone():
    """Guard mod falske positiver (samme fund som seng-projektets
    'found_keys_by_target'): en kørsel der selv finder 0 resultater (fx en
    bot-wall) må ALDRIG tolkes som "alt er solgt" for den kilde."""

    def _empty_fetch(config, dry_run=False):
        return []

    with LocalStore(":memory:") as store:
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a", "https://b"]), CONFIG)
        run_source(store, "kleinanzeigen", _empty_fetch, CONFIG)

        rows = {
            row["url"]: row["misses"]
            for row in store.connection.execute("SELECT url, misses FROM listings")
        }
    assert rows["https://a"] == 0
    assert rows["https://b"] == 0


def test_misses_only_counted_within_same_source_and_category():
    """En anden kildes/kategoris rækker må aldrig få misses talt op af en
    helt uafhængig kildes kørsel."""
    with LocalStore(":memory:") as store:
        run_source(store, "dba", _fetch_factory(["https://only-on-dba"]), CONFIG)
        run_source(store, "kleinanzeigen", _fetch_factory(["https://a"]), CONFIG)

        row = store.connection.execute(
            "SELECT misses FROM listings WHERE url = 'https://only-on-dba'"
        ).fetchone()
    assert row["misses"] == 0


def test_category_defaults_to_stoevsugere_and_attributes_json_is_empty_dict():
    """Regression -- kategori-generalisering (2026-10-03, se categories.py):
    run_source() uden et eksplicit category-argument skal fortsat skrive
    'stoevsugere' i den nye category-kolonne (bagudkompatibel default), og
    attributes_json skal være et tomt JSON-objekt, da stoevsuger-kategoriens
    normalize_listing() ikke sætter en 'attributes'-nøgle."""
    with LocalStore(":memory:") as store:
        run_source(store, "dba", _fake_fetch, CONFIG)
        row = store.connection.execute(
            "SELECT category, attributes_json, image_url FROM listings"
        ).fetchone()

    assert row["category"] == "stoevsugere"
    assert json.loads(row["attributes_json"]) == {}
    assert row["image_url"] is None
