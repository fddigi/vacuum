from __future__ import annotations

import pytest

from scraper_core.local_db import LocalStore
from scraper_core.sync import sync_pending


class FakeTursoClient:
    """Stand-in for TursoClient - records batches without touching the network,
    so delta-sync logic can be unit tested without a real Turso account."""

    def __init__(self):
        self.batches: list[list[tuple[str, dict]]] = []

    def batch(self, statements):
        self.batches.append(list(statements))
        return [None] * len(statements)


@pytest.fixture
def store(tmp_path):
    s = LocalStore(tmp_path / "local.db")
    yield s
    s.close()


def test_sync_pending_pushes_only_queued_rows(store):
    store.upsert_if_changed(
        source="dummy", item_key="1", payload={"item_key": "1", "title": "a"}, target_table="posts"
    )
    store.upsert_if_changed(
        source="dummy", item_key="2", payload={"item_key": "2", "title": "b"}, target_table="posts"
    )
    fake_turso = FakeTursoClient()

    synced_count = sync_pending(store, fake_turso)

    assert synced_count == 2
    assert len(fake_turso.batches) == 1
    assert len(fake_turso.batches[0]) == 2
    assert store.pending_sync_rows() == []  # everything marked synced, nothing left in outbox


def test_sync_pending_is_a_noop_when_queue_empty(store):
    fake_turso = FakeTursoClient()
    assert sync_pending(store, fake_turso) == 0
    assert fake_turso.batches == []


def test_sync_pending_generates_parameterized_upsert_sql(store):
    store.upsert_if_changed(
        source="dummy", item_key="1", payload={"item_key": "1", "title": "a"}, target_table="posts"
    )
    fake_turso = FakeTursoClient()
    sync_pending(store, fake_turso)

    sql, params = fake_turso.batches[0][0]
    assert "INSERT INTO posts" in sql
    assert "ON CONFLICT(item_key)" in sql
    assert params == {"item_key": "1", "title": "a"}
    # No raw values are interpolated into the SQL text itself:
    assert "'a'" not in sql
    assert '"a"' not in sql


def test_sync_pending_rejects_unsafe_table_name(store):
    # Force an unsafe target_table directly via the outbox to prove sync_pending
    # allow-lists identifiers rather than trusting stored data blindly.
    store.connection.execute(
        "INSERT INTO sync_queue (target_table, op, row_json) VALUES (?, ?, ?)",
        ("posts; DROP TABLE users;--", "insert", '{"item_key": "1"}'),
    )
    store.connection.commit()
    fake_turso = FakeTursoClient()

    with pytest.raises(ValueError):
        sync_pending(store, fake_turso)


def test_sync_pending_requires_conflict_column_in_payload(store):
    store.connection.execute(
        "INSERT INTO sync_queue (target_table, op, row_json) VALUES (?, ?, ?)",
        ("posts", "insert", '{"title": "no key field"}'),
    )
    store.connection.commit()
    fake_turso = FakeTursoClient()

    with pytest.raises(ValueError):
        sync_pending(store, fake_turso)


def test_sync_pending_respects_batch_size(store):
    for i in range(5):
        store.upsert_if_changed(
            source="dummy",
            item_key=str(i),
            payload={"item_key": str(i), "v": i},
            target_table="posts",
        )
    fake_turso = FakeTursoClient()

    synced_count = sync_pending(store, fake_turso, batch_size=2)

    assert synced_count == 2
    assert len(store.pending_sync_rows(limit=100)) == 3


# --- protected_update_columns / conditional_update_columns / enqueue_update ---
# Regression coverage for a real production bug (found independently via the
# vacuum project, 2026-09-19, matching seng's own 2026-07-23 first_seen fund):
# a manually-set column (e.g. a "dismissed" flag written directly to Turso by
# a Worker endpoint) was silently reset to the scraper's own default value on
# the very next resync triggered by an UNRELATED field changing, because the
# generic upsert SQL built here has no concept of "don't touch this column on
# an update". None of these scenarios were covered by any existing test in
# either project before this.


def test_enqueue_update_generates_a_plain_update_not_an_upsert(store):
    """enqueue_update() bypasses the content-hash check entirely -- its whole
    purpose is a partial payload (e.g. only item_key + last_seen) that would
    violate NOT NULL constraints if run through the INSERT...ON CONFLICT path
    used for genuinely new rows."""
    store.enqueue_update("posts", {"item_key": "1", "last_seen": "2026-09-19"})
    fake_turso = FakeTursoClient()

    synced_count = sync_pending(store, fake_turso)

    assert synced_count == 1
    sql, params = fake_turso.batches[0][0]
    assert sql.startswith("UPDATE posts SET")
    assert "ON CONFLICT" not in sql
    assert params == {"item_key": "1", "last_seen": "2026-09-19"}


def test_protected_update_columns_excluded_from_update_op_only(store):
    """The core regression: an 'update' op must never touch a protected
    column, even though the payload still legally carries it as a dict key."""
    store.enqueue_update(
        "listings", {"item_key": "1", "price_dkk": 500, "dismissed": 0, "dismissed_reason": None}
    )
    fake_turso = FakeTursoClient()

    sync_pending(store, fake_turso, protected_update_columns={"dismissed", "dismissed_reason"})

    sql, params = fake_turso.batches[0][0]
    assert "dismissed" not in sql
    assert "dismissed_reason" not in sql
    assert "price_dkk" in sql
    assert params == {"item_key": "1", "price_dkk": 500}  # protected keys dropped from params too


def test_protected_update_columns_do_not_affect_insert_op(store):
    """A genuinely NEW row (op='insert') must still write the scraper's
    default value for a normally-protected column - protection only applies
    to re-syncs of an already-existing row."""
    store.upsert_if_changed(
        source="dummy",
        item_key="1",
        payload={"item_key": "1", "dismissed": 0},
        target_table="listings",
    )
    fake_turso = FakeTursoClient()

    sync_pending(store, fake_turso, protected_update_columns={"dismissed"})

    sql, params = fake_turso.batches[0][0]
    assert "dismissed" in sql
    assert params == {"item_key": "1", "dismissed": 0}


def test_update_op_with_everything_protected_still_marks_synced(store):
    """If protection strips every non-conflict column, there is nothing left
    to update - the row must still be marked synced (a no-op SELECT) instead
    of retrying forever."""
    store.enqueue_update("listings", {"item_key": "1", "dismissed": 1})
    fake_turso = FakeTursoClient()

    synced_count = sync_pending(store, fake_turso, protected_update_columns={"dismissed"})

    assert synced_count == 1
    sql, _ = fake_turso.batches[0][0]
    assert sql.startswith("SELECT 1 FROM listings")
    assert store.pending_sync_rows() == []


def test_conditional_update_columns_used_instead_of_plain_assignment(store):
    store.enqueue_update("listings", {"item_key": "1", "brand": "Nilfisk"})
    fake_turso = FakeTursoClient()

    sync_pending(
        store,
        fake_turso,
        conditional_update_columns={
            "brand": "CASE WHEN brand_manual = 1 THEN brand ELSE :brand END"
        },
    )

    sql, params = fake_turso.batches[0][0]
    assert "CASE WHEN brand_manual = 1" in sql
    assert params == {"item_key": "1", "brand": "Nilfisk"}


def test_a_price_change_does_not_reset_a_protected_dismissed_flag():
    """End-to-end regression matching the exact production scenario: an
    already-dismissed item's PRICE changes (a real, legitimate content
    change) - the resulting resync must update price_dkk without reverting
    dismissed back to the scraper's own default of 0."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "local.db"
        store = LocalStore(db_path)
        try:
            store.connection.executescript(
                "CREATE TABLE listings (item_key TEXT PRIMARY KEY, price_dkk REAL, "
                "dismissed INTEGER NOT NULL DEFAULT 0)"
            )
            # First sync: genuinely new row.
            store.upsert_if_changed(
                source="dba",
                item_key="1",
                payload={"item_key": "1", "price_dkk": 1000, "dismissed": 0},
                target_table="listings",
            )
            fake_turso = FakeTursoClient()
            sync_pending(store, fake_turso, protected_update_columns={"dismissed"})
            # Simulate the row as it now exists on Turso (manually dismissed
            # there directly, exactly like the Worker's /dismiss endpoint).
            store.connection.execute("UPDATE listings SET dismissed = 1 WHERE item_key = ?", ("1",))
            store.connection.commit()

            # Second run: price genuinely changed (a real re-scrape) - the
            # scraper always computes dismissed=0 itself, since it has no
            # knowledge of the manual dismiss.
            changed = store.upsert_if_changed(
                source="dba",
                item_key="1",
                payload={"item_key": "1", "price_dkk": 900, "dismissed": 0},
                target_table="listings",
                hash_payload={"item_key": "1", "price_dkk": 900},
            )
            assert changed is True
            fake_turso2 = FakeTursoClient()
            sync_pending(store, fake_turso2, protected_update_columns={"dismissed"})

            sql, params = fake_turso2.batches[0][0]
            # The regression: dismissed must NOT appear in the generated SQL
            # at all for an update op, so Turso's already-dismissed row is
            # left untouched.
            assert "dismissed" not in sql
            assert "price_dkk" in sql
        finally:
            store.close()
