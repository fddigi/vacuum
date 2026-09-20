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
    for den fulde begrundelse -- ported uændret, kun DEFAULT_CATEGORY er ny.

    KRITISK RETTELSE (Opus 5-gennemgang, 2026-09-20): den oprindelige "seed
    KUN hvis tabellen er tom"-logik var skrøbelig i praksis -- en enkelt
    ad-hoc kørsel med en anden/mindre config (fx en manuel smoke-test-config
    med kun 3 søgeord) låste PERMANENT de forkerte termer ind i Turso,
    fordi enhver SENERE kørsel med den rigtige config.yaml (68+7 termer)
    fandt tabellen ikke-tom og aldrig genlæste den. Bekræftet konkret: alle
    scraper-kørsler indtil nu har kørt mod kun 3 termer, ikke specens fulde
    modelwhitelist. Rettet til at ALTID sikre config.yaml's termer findes
    (idempotent INSERT ... ON CONFLICT DO NOTHING pr. kørsel, ikke kun ved
    tom tabel) -- en term der allerede findes (uanset enabled-status,
    fx bevidst deaktiveret via webapp'en) røres ALDRIG, kun manglende
    termer tilføjes. config.yaml bliver dermed et "minimum garanteret sæt",
    ikke kun et engangs-udgangspunkt."""
    if turso is None:
        return _static_terms_from_config(vacuum_config)

    turso.execute(SEARCH_TERMS_SCHEMA)
    add_column_if_missing(
        turso, "search_terms", "category", f"TEXT NOT NULL DEFAULT '{DEFAULT_CATEGORY}'"
    )

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

    result = turso.execute("SELECT term, category FROM search_terms WHERE enabled = 1")
    logger.info("search_terms: %d aktive term(er) i Turso", len(result.rows))
    return [(row[0], row[1]) for row in result.rows]
