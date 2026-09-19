// API proxy Worker for this project's Turso database. One Worker per PROJECT,
// never one Worker per user. See README.md for the full auth model ("the padlock").

import { Hono } from "hono";
import { cors } from "hono/cors";

import { createSessionToken, verifyPassword } from "./auth";
import { resolveAllowedOrigin } from "./cors";
import { getDbClient } from "./db";
import { requireAuth } from "./middleware";
import { checkAndIncrementLoginAttempts } from "./rateLimit";
import type { Env, Variables } from "./types";

const app = new Hono<{ Bindings: Env; Variables: Variables }>();

// CORS locked to exactly one configurable Pages origin in production - never
// "*" - PLUS any localhost/127.0.0.1 origin for local dev (see cors.ts).
// `origin` needs env access, which in Hono is only available per-request,
// hence the wrapper. No `credentials: true` - that flag is for cookies, and
// auth here is a bearer token in an Authorization header instead (see
// middleware.ts for why).
app.use("*", async (c, next) => {
  const middleware = cors({
    origin: (requestOrigin) => resolveAllowedOrigin(requestOrigin, c.env.ALLOWED_ORIGIN),
    allowMethods: ["GET", "POST", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
  });
  return middleware(c, next);
});

app.get("/", (c) => c.json({ status: "ok" }));

app.post("/login", async (c) => {
  let body: { username?: string; password?: string };
  try {
    body = await c.req.json();
  } catch {
    body = {};
  }
  const { username, password } = body;
  if (!username || !password) {
    return c.json({ error: "username and password are required" }, 400);
  }

  const ip = c.req.header("CF-Connecting-IP") ?? "unknown";
  const { allowed } = await checkAndIncrementLoginAttempts(c.env.RATE_LIMIT_KV, ip, username);
  if (!allowed) {
    return c.json({ error: "too many login attempts - try again later" }, 429);
  }

  // v1 runs in "secret-mode": the one admin's credentials live as Worker secrets
  // (ADMIN_USER / ADMIN_PW_HASH), set by infra/add-user.sh --secret-mode. The
  // `users` table (see worker/migrations/0001_init.sql) already exists from v1
  // onwards so a project can move to --table-mode later by swapping this block
  // for a `SELECT * FROM users WHERE username = ?` lookup - no other API changes
  // needed, and a `user_id` FK can be threaded through the same way.
  if (username !== c.env.ADMIN_USER) {
    return c.json({ error: "invalid credentials" }, 401);
  }
  const valid = await verifyPassword(password, c.env.ADMIN_PW_HASH);
  if (!valid) {
    return c.json({ error: "invalid credentials" }, 401);
  }

  const maxAgeDays = Number(c.env.SESSION_TOKEN_MAX_AGE_DAYS ?? "30");
  const maxAgeSeconds = maxAgeDays * 24 * 60 * 60;
  const token = await createSessionToken(
    { sub: username, role: "admin", exp: Math.floor(Date.now() / 1000) + maxAgeSeconds },
    c.env.SESSION_HMAC_SECRET,
  );

  // Token goes in the JSON body, not a cookie - the frontend stores it in
  // localStorage and sends it back as `Authorization: Bearer <token>`. See
  // middleware.ts for why a cookie doesn't work here (Safari ITP).
  return c.json({ ok: true, username, role: "admin", token });
});

// Stateless tokens (no server-side session store) - there is nothing to
// revoke server-side, so /logout exists mainly for symmetry/future use
// (e.g. a denylist) and to require a valid token before acknowledging.
// The actual logout action is the frontend deleting its localStorage token.
app.post("/logout", requireAuth, (c) => {
  return c.json({ ok: true });
});

app.get("/api/me", requireAuth, (c) => {
  const session = c.get("session");
  return c.json({ username: session.sub, role: session.role });
});

// --- Data endpoints against the `listings` table (matches
// scraper/scraper/pipeline.py and worker/migrations/0001_init.sql). Display-only:
// the scraper writes exclusively via scraper-core's delta-sync outbox, so there
// is no POST /api/listings write endpoint. ---

const DEFAULT_CATEGORY = "Sikkerhedsstøvsuger";

async function ensureColumn(
  db: ReturnType<typeof getDbClient>,
  table: string,
  column: string,
  ddl: string,
): Promise<void> {
  const result = await db.execute(`PRAGMA table_info(${table})`);
  const existingColumns = new Set(result.rows.map((row) => row.name as string));
  if (existingColumns.has(column)) {
    return;
  }
  await db.execute(`ALTER TABLE ${table} ADD COLUMN ${column} ${ddl}`);
}

app.get("/api/listings", requireAuth, async (c) => {
  const db = getDbClient(c.env);
  const limit = Math.min(Number(c.req.query("limit") ?? "500") || 500, 2000);

  // Filtre matcher en fremtidig frontend-dropdown for vurdering/mærke/kilde.
  const vurdering = c.req.query("vurdering");
  const brand = c.req.query("brand");
  const source = c.req.query("source");
  const dustClass = c.req.query("dust_class");
  const includeDismissed = c.req.query("include_dismissed") === "1";

  await ensureColumn(db, "listings", "dismissed", "INTEGER NOT NULL DEFAULT 0");
  await ensureColumn(db, "listings", "dismissed_reason", "TEXT");

  const conditions: string[] = [];
  const args: (string | number)[] = [];
  if (vurdering) {
    conditions.push("vurdering = ?");
    args.push(vurdering);
  }
  if (brand) {
    conditions.push("brand = ?");
    args.push(brand);
  }
  if (source) {
    conditions.push("source = ?");
    args.push(source);
  }
  if (dustClass) {
    conditions.push("dust_class = ?");
    args.push(dustClass);
  }
  // Afviste annoncer skjules som standard - se "Vis afviste"-tjekboksen i
  // frontend/index.html, som sætter include_dismissed=1 for at se dem igen.
  if (!includeDismissed) {
    conditions.push("dismissed = 0");
  }
  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";

  // Sortering: "billigst" (default) og "nyeste" - se frontend/index.html's
  // dropdown. `price_dkk IS NULL, price_dkk ASC` sætter annoncer uden pris
  // (typisk auktioner uden aktuelt bud) sidst i stedet for først (SQLite
  // sorterer NULL som den laveste værdi som standard, hvilket ellers ville
  // give en tom pris "billigst").
  const sort = c.req.query("sort") === "newest" ? "newest" : "price_asc";
  const orderBy =
    sort === "newest"
      ? "first_seen DESC"
      : "price_dkk IS NULL, price_dkk ASC, first_seen DESC";

  args.push(limit);

  // Idempotent: undgår en "no such table"-fejl hvis endpointet rammes før
  // scraperen nogensinde har logget et prisfald.
  await db.execute(
    `CREATE TABLE IF NOT EXISTS price_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      item_key TEXT NOT NULL, old_price_dkk REAL NOT NULL,
      new_price_dkk REAL NOT NULL, pct_change REAL NOT NULL,
      old_vurdering TEXT, new_vurdering TEXT, observed_at TEXT NOT NULL
    )`,
  );

  // Spec: "marker annoncer der har ligget over 30 dage som forhandlings-
  // mulighed" -- ren query-tids-udledning af first_seen, ingen separat kolonne
  // (undgår at et beregnet felt kan blive stale mellem scraper-kørsler).
  const result = await db.execute({
    sql: `SELECT listings.*,
      (julianday('now') - julianday(first_seen)) >= 30 AS forhandlingsmulighed,
      (SELECT pct_change FROM price_history ph
        WHERE ph.item_key = listings.item_key ORDER BY ph.id DESC LIMIT 1) AS latest_price_drop_pct,
      (SELECT observed_at FROM price_history ph
        WHERE ph.item_key = listings.item_key ORDER BY ph.id DESC LIMIT 1) AS latest_price_drop_at
      FROM listings ${where}
      ORDER BY ${orderBy}
      LIMIT ?`,
    args,
  });
  return c.json({ listings: result.rows });
});

app.get("/api/listings/:itemKey", requireAuth, async (c) => {
  const db = getDbClient(c.env);
  const itemKey = c.req.param("itemKey");
  if (!itemKey) {
    return c.json({ error: "itemKey is required" }, 400);
  }
  const result = await db.execute({
    sql: "SELECT * FROM listings WHERE item_key = ?",
    args: [itemKey],
  });
  if (result.rows.length === 0) {
    return c.json({ error: "not found" }, 404);
  }
  return c.json({ listing: result.rows[0] });
});

// --- Manuel afvisning ("diskvalificér"-knappen i frontend'en), ported fra
// seng-projektets samme mønster. Skriver direkte til Turso UDENOM scraperen -
// se scraper/scraper/pipeline.py's ON CONFLICT-klausul for hvorfor scraperens
// egen næste kørsel aldrig overskriver dette. ---

app.post("/api/listings/:itemKey/dismiss", requireAuth, async (c) => {
  const db = getDbClient(c.env);
  const itemKey = c.req.param("itemKey");
  if (!itemKey) {
    return c.json({ error: "itemKey is required" }, 400);
  }
  await ensureColumn(db, "listings", "dismissed", "INTEGER NOT NULL DEFAULT 0");
  await ensureColumn(db, "listings", "dismissed_reason", "TEXT");
  await db.execute({
    sql: "UPDATE listings SET dismissed = 1, dismissed_reason = 'manual' WHERE item_key = ?",
    args: [itemKey],
  });
  return c.json({ ok: true });
});

app.post("/api/listings/:itemKey/undismiss", requireAuth, async (c) => {
  const db = getDbClient(c.env);
  const itemKey = c.req.param("itemKey");
  if (!itemKey) {
    return c.json({ error: "itemKey is required" }, 400);
  }
  await ensureColumn(db, "listings", "dismissed", "INTEGER NOT NULL DEFAULT 0");
  await ensureColumn(db, "listings", "dismissed_reason", "TEXT");
  await db.execute({
    sql: "UPDATE listings SET dismissed = 0, dismissed_reason = NULL WHERE item_key = ?",
    args: [itemKey],
  });
  return c.json({ ok: true });
});

// --- Dynamiske søgetermer ("ønskeseddel"), se scraper/scraper/search_terms.py. ---

app.get("/api/search-terms", requireAuth, async (c) => {
  const db = getDbClient(c.env);
  await ensureColumn(db, "search_terms", "category", `TEXT NOT NULL DEFAULT '${DEFAULT_CATEGORY}'`);
  const result = await db.execute(
    "SELECT term, category, enabled, created_at FROM search_terms ORDER BY created_at DESC",
  );
  return c.json({ searchTerms: result.rows });
});

app.post("/api/search-terms", requireAuth, async (c) => {
  const body = await c.req.json().catch(() => ({}));
  const term = typeof body.term === "string" ? body.term.trim() : "";
  if (!term) {
    return c.json({ error: "term is required" }, 400);
  }
  const category =
    typeof body.category === "string" && body.category.trim() ? body.category.trim() : DEFAULT_CATEGORY;
  const db = getDbClient(c.env);
  await ensureColumn(db, "search_terms", "category", `TEXT NOT NULL DEFAULT '${DEFAULT_CATEGORY}'`);
  await db.execute({
    sql: `INSERT INTO search_terms (term, category, enabled, created_at) VALUES (?, ?, 1, ?)
          ON CONFLICT(term) DO UPDATE SET enabled = 1, category = excluded.category`,
    args: [term, category, new Date().toISOString()],
  });
  return c.json({ ok: true, term, category });
});

app.delete("/api/search-terms/:term", requireAuth, async (c) => {
  const term = c.req.param("term");
  if (!term) {
    return c.json({ error: "term is required" }, 400);
  }
  const db = getDbClient(c.env);
  await db.execute({ sql: "DELETE FROM search_terms WHERE term = ?", args: [term] });
  return c.json({ ok: true });
});

export default app;
