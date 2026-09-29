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


def config_for_source(vacuum_config: dict, source_name: str) -> dict:
    """Returnerer en config hvor `search_terms.secondary` er netop DENNE kildes
    supplerende søgeord (config.yaml's `search_terms.per_source`).

    HVORFOR PER KILDE OG IKKE GLOBALT (ny 2026-09-29, Opus-review af intake):
    søgeordene har hidtil været fuldstændig globale -- main.py gav den samme
    flade liste til alle otte kilder. To tidligere reviews flaggede at det
    blokerer for at hjælpe de kilder der har DÅRLIG frase-søgning, uden
    samtidig at drukne dem der allerede fungerer. Live-målt 2026-09-29:

      * klaravik.dk fandt 0 træf på 'sikkerhedsstøvsuger' og 0 på
        'Nilfisk Attix 33-2H' (et af vores 63 produktionssøgeord), men 1 træf
        på det bare 'støvsuger' -- og det ene træf er præcis den annonce
        brugeren efterlyste: "Industristøvsugere Electrostar Starmix IS 2
        styk". Klaravik matcher på delstreng, så ét kort ord har langt bedre
        recall end en flerords-frase.
      * auktionshuset.dk gav 31 lots på det bare 'støvsuger' mod en håndfuld
        på fraserne -- kilden er en konkursauktion, hvor lot-titler er
        "<Kategori> <MÆRKE> <model>" og sjældent indeholder vores fraser.
      * dba.dk gav derimod 54 træf på det bare mærkeord 'Nilfisk', hvoraf
        INGEN var H-klasse (højtryksrensere, vinduespudsere, Buddy/One/Elite-
        husholdningsstøvsugere). Samme flodbølge ville ramme blocket.se og
        kleinanzeigen.de, som allerede fungerer godt med de specifikke
        modelfraser. Derfor er brede termer bevidst IKKE lagt i den globale
        liste.
      * retrade.eu gav 1 træf på seks brede termer tilsammen (en fejemaskine,
        'Nilfisk City Ranger 3500'), og 0 på både 'støvsuger' og
        'dammsugare'. Kilden har intet udbud i kategorien overhovedet, så den
        får BEVIDST intet supplement -- bredere søgning kan ikke finde noget
        der ikke er der.

    Supplementerne seedes med vilje ALDRIG til Turso's search_terms-tabel
    (_static_terms_from_config læser kun primary/secondary): tabellen er den
    globale, webapp-redigerbare ønskeseddel, og et kildespecifikt søgeord
    hører ikke hjemme der -- det ville gøre det globalt igen ved næste
    kørsel."""
    per_source = (vacuum_config.get("search_terms") or {}).get("per_source") or {}
    extra = list(per_source.get(source_name) or [])
    if not extra:
        return vacuum_config
    logger.info(
        "search_terms: %s får %d kildespecifik(ke) ekstra term(er)", source_name, len(extra)
    )
    # LÆGGES OVEN I secondary, erstatter den ALDRIG: i Turso-tilstand er
    # secondary tom (main.py flader alle termer ud i primary), men i
    # lokal-only-tilstand indeholder den config.yaml's ~57 modelfraser, og de
    # må ikke forsvinde bare fordi kilden også har et supplement.
    existing = list(vacuum_config["search_terms"].get("secondary") or [])
    merged = existing + [t for t in extra if t not in existing]
    return {
        **vacuum_config,
        "search_terms": {**vacuum_config["search_terms"], "secondary": merged},
    }
