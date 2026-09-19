"""Per-kilde kadence. Alle kilder deler ét launchd-interval (spec: "kør hver
6. time"), men bot-følsomme kilder (Kleinanzeigen/Blocket) øger blokerings-
risiko ved for hyppig hentning. Denne fil lader ét fælles schema give
differentieret kadence pr. kilde uden flere launchd-jobs.

Ported uændret fra PASPEAKERS -- ren lokal bogføring (last_run pr. kilde),
synkroniseres bevidst IKKE til Turso.
"""

from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

SOURCE_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_state (
    source TEXT PRIMARY KEY,
    last_run_at TEXT NOT NULL
);
"""


def should_run_source(
    conn, source_name: str, min_interval_hours: dict, force: bool = False
) -> bool:
    """True hvis kilden bør køre nu. `force=True` (fra --source <navn>)
    ignorerer altid min-interval -- manuel fejlsøgning skal altid kunne køre."""
    if force:
        return True

    min_hours = min_interval_hours.get(source_name)
    if min_hours is None:
        return True

    row = conn.execute(
        "SELECT last_run_at FROM source_state WHERE source = ?", (source_name,)
    ).fetchone()
    if row is None:
        return True

    last_run = datetime.datetime.fromisoformat(row[0])
    elapsed_hours = (datetime.datetime.now(datetime.UTC) - last_run).total_seconds() / 3600
    if elapsed_hours < min_hours:
        logger.info(
            "%s: sprunget over - kørte for %.1f time(r) siden (min. interval: %dt)",
            source_name,
            elapsed_hours,
            min_hours,
        )
        return False
    return True


def mark_source_run(conn, source_name: str) -> None:
    now = datetime.datetime.now(datetime.UTC).isoformat()
    conn.execute(
        "INSERT INTO source_state (source, last_run_at) VALUES (?, ?) "
        "ON CONFLICT(source) DO UPDATE SET last_run_at = excluded.last_run_at",
        (source_name, now),
    )
    conn.commit()
