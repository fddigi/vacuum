-- Applied once per project against its Turso database. In this template that
-- happens as part of infra/provision.sh; there is no separate migration runner.
--
-- v1 runs in "secret-mode" (see infra/add-user.sh --secret-mode) and does not
-- read from the `users` table at all - it exists from the start so a project can
-- be upgraded to --table-mode later without any API rewrite.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    role TEXT NOT NULL DEFAULT 'admin'
);

-- Brugte H/M-klasse sikkerhedsstøvsuger-annoncer, matcher
-- scraper/scraper/pipeline.py's LOCAL_SCHEMA/TURSO_SCHEMA og
-- worker/src/index.ts's /api/listings-endpoint.
CREATE TABLE IF NOT EXISTS listings (
    item_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT,
    url TEXT,
    location TEXT,
    brand TEXT,
    model_key TEXT,
    model_label TEXT,
    dust_class TEXT,
    klasse_kilde TEXT,
    asbestos_approved TEXT,
    container_l REAL,
    battery INTEGER NOT NULL DEFAULT 0,
    price_dkk REAL,
    landed_price_dkk REAL,
    shipping_customs_dkk REAL,
    origin_country TEXT,
    filterrensning TEXT,
    flowsensor TEXT,
    stikdaase TEXT,
    medfoelger TEXT,
    score INTEGER,
    vurdering TEXT,
    classification_method TEXT,
    mangler_info TEXT,
    spoergsmaal_til_saelger TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT,
    raw_json TEXT
);

-- Dynamiske søgetermer ("ønskeseddel"), redigerbar fra webapp'en -- se
-- scraper/scraper/search_terms.py og worker/src/index.ts's
-- /api/search-terms-endpoints.
CREATE TABLE IF NOT EXISTS search_terms (
    term TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Sikkerhedsstøvsuger'
);

-- Prisfalds-detektion, rent append -- se scraper/scraper/price_history.py.
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
