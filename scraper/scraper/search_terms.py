"""Dynamiske søgetermer ("ønskeseddel"), ported fra PASPEAKERS/PLAGG-mønsteret:
listen over ting der skal søges efter lever i Turso når den er konfigureret,
redigerbar fra webapp'en i stedet for at kræve en config.yaml-redigering +
redeploy for hver ændring.

Falder tilbage til config.yaml's statiske search_terms.primary/secondary-lister
når Turso ikke er konfigureret (lokal-only mode).
"""

from __future__ import annotations

import datetime
import logging

from scraper_core.turso_client import TursoClient

from .schema_utils import add_column_if_missing

logger = logging.getLogger(__name__)

DEFAULT_CATEGORY = "Sikkerhedsstøvsuger"

SEARCH_TERMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_terms (
    term TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""


def _static_terms_from_config(vacuum_config: dict) -> list[tuple[str, str]]:
    st = vacuum_config.get("search_terms", {})
    terms = list(st.get("primary", [])) + list(st.get("secondary", []))
    return [(term, DEFAULT_CATEGORY) for term in terms]


def load_search_terms(vacuum_config: dict, turso: TursoClient | None) -> list[tuple[str, str]]:
    """Returnerer de aktive (term, kategori)-par. Se PASPEAKERS' search_terms.py
    for den fulde begrundelse -- ported uændret, kun DEFAULT_CATEGORY er ny."""
    if turso is None:
        return _static_terms_from_config(vacuum_config)

    turso.execute(SEARCH_TERMS_SCHEMA)
    add_column_if_missing(
        turso, "search_terms", "category", f"TEXT NOT NULL DEFAULT '{DEFAULT_CATEGORY}'"
    )
    result = turso.execute("SELECT term, category FROM search_terms WHERE enabled = 1")
    if result.rows:
        return [(row[0], row[1]) for row in result.rows]

    static_terms = _static_terms_from_config(vacuum_config)
    if static_terms:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        turso.batch(
            [
                (
                    "INSERT INTO search_terms (term, category, enabled, created_at) "
                    "VALUES (?, ?, 1, ?) ON CONFLICT(term) DO NOTHING",
                    (term, category, now),
                )
                for term, category in static_terms
            ]
        )
        logger.info(
            "search_terms: seeded %d term(s) from config.yaml into Turso", len(static_terms)
        )
    return static_terms
