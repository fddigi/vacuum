"""Prisfalds-detektion. Append-only log af faktiske prisfald på allerede
kendte annoncer. Relevant for spec's "marker annoncer der har ligget over 30
dage som forhandlingsmulighed" -- et prisfald er et nært beslægtet signal om
at sælger er villig til at forhandle (se pipeline.py for selve 30-dages-alder-
beregningen, som er en separat, ren query-tids-udledning af first_seen).

Ported uændret fra PASPEAKERS -- ren observation af det pipeline.py allerede
opdager, ingen separat genbesøgs-crawler.
"""

from __future__ import annotations

PRICE_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT NOT NULL,
    old_price_dkk REAL NOT NULL,
    new_price_dkk REAL NOT NULL,
    pct_change REAL NOT NULL,
    old_vurdering TEXT,
    new_vurdering TEXT,
    observed_at TEXT NOT NULL
);
"""


def sync_price_history_to_turso(turso, events: list[dict]) -> None:
    turso.execute(PRICE_HISTORY_SCHEMA)
    if not events:
        return
    turso.batch(
        [
            (
                "INSERT INTO price_history (item_key, old_price_dkk, new_price_dkk, "
                "pct_change, old_vurdering, new_vurdering, observed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    e["item_key"],
                    e["old_price_dkk"],
                    e["new_price_dkk"],
                    e["pct_change"],
                    e["old_vurdering"],
                    e["new_vurdering"],
                    e["observed_at"],
                ),
            )
            for e in events
        ]
    )
