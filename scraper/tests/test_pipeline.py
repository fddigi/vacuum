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
