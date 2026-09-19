"""Lille hjælper til additive, idempotente skemamigreringer (ALTER TABLE ADD
COLUMN) på tabeller der allerede eksisterede FØR en ny kolonne blev tilføjet.
`CREATE TABLE IF NOT EXISTS` alene tilføjer IKKE en kolonne retroaktivt til en
allerede-eksisterende tabel -- hverken på den lokale SQLite-fil eller i Turso.

Ported uændret fra PASPEAKERS/seng -- se den originale docstring for hvorfor
"forsøg ALTER og fang fejlen bagefter" ikke virker pålideligt mod Turso.
"""

from __future__ import annotations


def add_column_if_missing(conn, table: str, column: str, column_ddl: str) -> None:
    """`conn` er hvad som helst med en `.execute(sql)` -- en sqlite3.Connection
    eller en TursoClient. Tjekker via `PRAGMA table_info` FØR den forsøger
    ALTER, i stedet for at forsøge ALTER og fange en "duplicate column"-fejl
    bagefter (upålideligt mod Turso's HTTP-transport, se scraper-boilerplates
    SCRAPING_LESSONS.md)."""
    result = conn.execute(f"PRAGMA table_info({table})")
    rows = result.rows if hasattr(result, "rows") else result.fetchall()
    existing_columns = {row[1] for row in rows}
    if column in existing_columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_ddl}")
