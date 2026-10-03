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

// Prioriterede modeller (2026-09-28, brugerens stovsuger-modeloversigt.md,
// afsnit 3A/3B/3C) -- samme model_keys som scraper/scraper/models.py's
// priority_stars-felt (3=A/2=B/1=C), se scraper.models.priority_model_keys().
// Duplikeret her fordi Worker'en er TypeScript, ikke Python (samme princip
// som config.yaml's søgetermer duplikerer models.py's whitelist) -- hold i
// sync hvis priority_stars ændres i models.py.
const PRIORITY_3_STARS = [
  "bona_dcs25",
  "flex_vce44h_ac",
  "nilfisk_attix_30_0h",
  "nilfisk_attix_30_2h",
  "nilfisk_attix_33_2h",
  "nilfisk_attix_44_2h",
  "nilfisk_attix_50_0h",
  "nilfisk_attix_550_0h",
  "nilfisk_attix_751_0h",
  "nilfisk_attix_965",
  "nilfisk_attix_995",
  "nilfisk_ivb5h",
  "nilfisk_ivb7h",
  "nilfisk_ivb965_sd_xc",
  "ronda_h_serie",
  "starmix_isc_h1225_asbest",
];
// "baier_bss608h" tilføjet 2026-09-29 (stovsuger-modeloversigt2.md, version 3,
// afsnit 5 + 7A): ★★ og ikke ★★★, fordi modellens egen række i afsnit 7A's
// tabel har "Sikkerhedspose: ikke fundet" -- se models.py's baier_bss608h-note.
const PRIORITY_2_STARS = ["baier_bss608h", "nilfisk_aero_21h", "nilfisk_aero_26_2h_pc"];
const PRIORITY_1_STAR = [
  "bosch_gas35h_afc",
  "bygma_isc_h163_safe",
  "festool_cth26e",
  "festool_cth26ei",
  "festool_cth48e",
  "hilti_vc40h_x",
  "karcher_nt_h_serie",
  "makita_vc3211h",
  "metabo_asa30h_pc",
  "metabo_asr35h_acp",
  "starmix_energetic_1420h",
  "starmix_energetic_sx110080h",
  "starmix_ipulse_h1635_safe_plus",
  "starmix_isc_h1625",
];

function sqlInList(keys: string[]): string {
  return keys.map((k) => `'${k}'`).join(", ");
}

const PRIORITET_CASE_SQL = `CASE
  WHEN model_key IN (${sqlInList(PRIORITY_3_STARS)}) THEN 3
  WHEN model_key IN (${sqlInList(PRIORITY_2_STARS)}) THEN 2
  WHEN model_key IN (${sqlInList(PRIORITY_1_STAR)}) THEN 1
  ELSE 0
END AS prioritet`;

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
  // "sources" (flertal, komma-separeret) erstatter den tidligere ental-
  // dropdown "source" (2026-09-28) -- frontend'en håndterer nu hver kilde
  // uafhængigt via afkrydsningsfelter (bl.a. så kleinanzeigen kan slås fra
  // som default, se frontend/index.html), i stedet for ét enkelt valg.
  const sourcesParam = c.req.query("sources");
  const sources = sourcesParam
    ? sourcesParam
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
    : null;
  const dustClass = c.req.query("dust_class");
  const includeDismissed = c.req.query("include_dismissed") === "1";
  const validatedOnly = c.req.query("validated") === "1";
  // Kategori-generalisering (2026-10-03, se scraper/scraper/categories.py's
  // docstring): "vacuum" dækker nu hele SHV-sourcingen, ikke kun
  // sikkerhedsstøvsugere. Ingen filter = alle kategorier (i dag betyder det
  // reelt "alle", da kun 'stoevsugere' findes endnu) -- frontend'ens
  // fremtidige faneblade pr. kategori sender denne eksplicit.
  const category = c.req.query("category");

  await ensureColumn(db, "listings", "dismissed", "INTEGER NOT NULL DEFAULT 0");
  await ensureColumn(db, "listings", "dismissed_reason", "TEXT");
  await ensureColumn(db, "listings", "category", "TEXT NOT NULL DEFAULT 'stoevsugere'");
  await ensureColumn(db, "listings", "image_url", "TEXT");
  await ensureColumn(db, "listings", "attributes_json", "TEXT");

  const conditions: string[] = [];
  const args: (string | number)[] = [];
  if (category) {
    conditions.push("category = ?");
    args.push(category);
  }
  if (vurdering) {
    conditions.push("vurdering = ?");
    args.push(vurdering);
  }
  if (brand) {
    conditions.push("brand = ?");
    args.push(brand);
  }
  if (sources && sources.length > 0) {
    conditions.push(`source IN (${sources.map(() => "?").join(", ")})`);
    args.push(...sources);
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
  // "Valideret" (Opus 5-anbefaling, 2026-09-20): en UAFHÆNGIG akse fra
  // vurdering ("er klassen bekræftet?" vs. "er det et godt køb?") - se
  // `valideret`-feltet i SELECT-listen nedenfor for den fulde begrundelse
  // for hvorfor definitionen er identisk her og der (skal aldrig afvige).
  if (validatedOnly) {
    conditions.push("model_key IS NOT NULL AND klasse_kilde = 'modelnavn' AND dust_class = 'H'");
  }
  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";

  // Sortering: "billigst" (default) og "nyeste" - se frontend/index.html's
  // dropdown. `price_dkk IS NULL, price_dkk ASC` sætter annoncer uden pris
  // (typisk auktioner uden aktuelt bud) sidst i stedet for først (SQLite
  // sorterer NULL som den laveste værdi som standard, hvilket ellers ville
  // give en tom pris "billigst").
  const sortParam = c.req.query("sort");
  const sort = sortParam === "newest" || sortParam === "priority" ? sortParam : "price_asc";
  const orderBy =
    sort === "newest"
      ? "first_seen DESC"
      : sort === "priority"
        // SQLite tillader ORDER BY på en SELECT-liste-alias (se "prioritet"
        // nedenfor) -- ingen grund til at duplikere CASE-udtrykket her.
        ? "prioritet DESC, price_dkk IS NULL, price_dkk ASC"
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
  //
  // "Valideret" (Opus 5-anbefaling, 2026-09-20, efter en kritisk gennemgang
  // af live søgeresultater mod opdraget): betyder "støvklassen er BEKRÆFTET
  // via et faktisk modelnavn-match", IKKE "værd at købe" -- de to akser
  // holdes bevidst uafhængige (en valideret maskine kan sagtens være
  // 'afvist' på pris, se WHERE-klausulens ?validated=1-håndtering ovenfor).
  // Beregnet her, IKKE i Python/classify.py, af samme grund som
  // forhandlingsmulighed: en boolesk kolonne skrevet af scraperen ville
  // kun opdateres når rækken genbesøges, og ville stå stale for alle
  // allerede-scrapede rækker hver gang definitionen justeres. dust_class
  // er bevidst kun 'H' (ikke også 'M') -- se README's M-klasse-afsnit.
  const result = await db.execute({
    sql: `SELECT listings.*,
      (julianday('now') - julianday(first_seen)) >= 30 AS forhandlingsmulighed,
      (model_key IS NOT NULL AND klasse_kilde = 'modelnavn' AND dust_class = 'H') AS valideret,
      ${PRIORITET_CASE_SQL},
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
