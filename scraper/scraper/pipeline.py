"""Adapter-lag der forbinder normalize.py/classify.py til scraper-core's
delta-sync-mønster (LocalStore.upsert_if_changed + Turso-outboxen). Samme
`run_source()` genbruges af alle kilder -- kun `fetch()` selv er forskellig
pr. kilde. Struktur ported fra PASPEAKERS' pipeline.py, men med et helt nyt
skema der matcher spec'ens JSON-outputformat i stedet for PA-højttalernes.

"afstand_km" fra spec's output-JSON er BEVIDST UDELADT: det kræver geokodning
af sælgers lokationstekst mod en fast radius (fx 2000 Frederiksberg), hvilket
denne v1 ikke implementerer -- se README/BACKLOG for hvordan det kan tilføjes
senere uden skemaændring (kolonnen kan tilføjes additivt, se schema_utils.py).
"""

from __future__ import annotations

import datetime
import json
import logging

from scraper_core.local_db import LocalStore
from scraper_core.watchdog import SourceTimeoutError, run_with_timeout

from .categories import DEFAULT_CATEGORY, Category
from .schema_utils import add_column_if_missing

logger = logging.getLogger(__name__)

TARGET_TABLE = "listings"

# Passed to scraper_core.sync.sync_pending() (see main.py) -- columns a manual
# Worker endpoint owns and that must NEVER be touched by a scraper resync,
# even when other real content changed on the same row. Uden dette nulstiller
# den generiske Turso-upsert-SQL i sync_pending() stille disse felter til
# scraperens egen (konstante) default-værdi, hver gang en anden ændring på
# rækken udløser en re-sync -- se scraper_core.sync.sync_pending()'s
# docstring for det konkrete produktionsfund (samme klasse bug som ramte
# seng-projektets first_seen, fundet uafhængigt her via dismissed).
SYNC_PROTECTED_COLUMNS = {"first_seen", "dismissed", "dismissed_reason"}

LOCAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    item_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'stoevsugere',
    title TEXT,
    url TEXT,
    image_url TEXT,
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
    raw_json TEXT,
    dismissed INTEGER NOT NULL DEFAULT 0,
    dismissed_reason TEXT,
    attributes_json TEXT,
    misses INTEGER NOT NULL DEFAULT 0,
    sold_marker INTEGER NOT NULL DEFAULT 0
);
"""
TURSO_SCHEMA = LOCAL_SCHEMA

# dismissed/dismissed_reason: manuel afvisning fra frontend'en (via Worker'ens
# POST /api/listings/:itemKey/dismiss, som skriver direkte til Turso UDENOM
# scraperen) -- ported fra seng-projektets samme mønster. Sættes KUN ved en
# annonces FØRSTE indsættelse her (default 0/NULL) -- en senere re-sync (fx et
# prisfald) rører ALDRIG disse to kolonner (bevidst udeladt fra ON CONFLICT
# DO UPDATE SET nedenfor), så en brugers manuelle afvisning aldrig
# overskrives af scraperen ved næste kørsel.
_INSERT_SQL = """
INSERT INTO listings (item_key, source, category, title, url, image_url, location,
    brand, model_key, model_label, dust_class, klasse_kilde, asbestos_approved,
    container_l, battery, price_dkk, landed_price_dkk, shipping_customs_dkk,
    origin_country, filterrensning, flowsensor, stikdaase, medfoelger, score,
    vurdering, classification_method, mangler_info, spoergsmaal_til_saelger,
    attributes_json, first_seen, last_seen, raw_json, dismissed, dismissed_reason)
VALUES (:item_key, :source, :category, :title, :url, :image_url, :location,
    :brand, :model_key, :model_label, :dust_class, :klasse_kilde, :asbestos_approved,
    :container_l, :battery, :price_dkk, :landed_price_dkk, :shipping_customs_dkk,
    :origin_country, :filterrensning, :flowsensor, :stikdaase, :medfoelger, :score,
    :vurdering, :classification_method, :mangler_info, :spoergsmaal_til_saelger,
    :attributes_json, :first_seen, :last_seen, :raw_json, :dismissed, :dismissed_reason)
ON CONFLICT(item_key) DO UPDATE SET
    category = excluded.category, title = excluded.title, url = excluded.url,
    image_url = excluded.image_url, location = excluded.location,
    brand = excluded.brand, model_key = excluded.model_key,
    model_label = excluded.model_label, dust_class = excluded.dust_class,
    klasse_kilde = excluded.klasse_kilde, asbestos_approved = excluded.asbestos_approved,
    container_l = excluded.container_l, battery = excluded.battery,
    price_dkk = excluded.price_dkk, landed_price_dkk = excluded.landed_price_dkk,
    shipping_customs_dkk = excluded.shipping_customs_dkk,
    origin_country = excluded.origin_country, filterrensning = excluded.filterrensning,
    flowsensor = excluded.flowsensor, stikdaase = excluded.stikdaase,
    medfoelger = excluded.medfoelger, score = excluded.score, vurdering = excluded.vurdering,
    classification_method = excluded.classification_method,
    mangler_info = excluded.mangler_info,
    spoergsmaal_til_saelger = excluded.spoergsmaal_til_saelger,
    attributes_json = excluded.attributes_json,
    raw_json = excluded.raw_json, last_seen = excluded.last_seen,
    -- Rækken bliver kun genskrevet via denne gren når den rent faktisk blev
    -- GENFUNDET i denne kørsel (se run_source() nedenfor) -- nulstil derfor
    -- altid misses her, uanset dens tidligere værdi.
    misses = 0
    -- dismissed/dismissed_reason er BEVIDST udeladt her, se kommentaren
    -- ovenfor, og det samme gælder sold_marker: KUN
    -- kleinanzeigen.verify_sold_status() (kaldt separat fra main.py, se
    -- dens docstring) må sætte/rydde det feltet, via en direkte UPDATE
    -- udenom denne SQL -- ellers ville en helt almindelig prisændring her
    -- nulstille et allerede bekræftet "solgt"-flag tilbage til 0, fordi en
    -- normal fetch() (kun søgeresultat-kort) aldrig selv kan vide om en
    -- allerede-gemt annonce sidenhen er blevet solgt.
"""


def _bool_or_unknown_to_text(value) -> str:
    """normalize.py's flowsensor/stikdaase-felter er enten True eller den
    bogstavelige streng 'ukendt' (aldrig False -- fravær af omtale er ikke
    bevis for fravær af funktionen, se normalize.py). asbestos_approved KAN
    derimod være True/False/None (en model-kendsgerning, ikke kun tekst-
    omtale), så denne hjælper dækker begge tilfælde ensartet for DB-lagring."""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "ukendt"


def make_item_key(
    source: str, url: str | None, title: str | None = None, price_dkk: float | None = None
) -> str:
    import hashlib

    basis = f"{source}|{url}" if url else f"{source}|{title}|{price_dkk}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


def run_source(
    store: LocalStore,
    source_name: str,
    fetch_fn,
    config: dict,
    category: Category = DEFAULT_CATEGORY,
    dry_run: bool = False,
    fetch_timeout_seconds: float = 300,
) -> tuple[int, int, list[dict]]:
    """Kører én kildes fetch() -> normalize -> classify -> upsert_if_changed,
    for ÉN kategori ad gangen (default: stoevsugere, se categories.py).
    Isoleret try/except pr. kilde -- én kildes fejl må aldrig vælte de andre.

    Returnerer (raw_count, changed_count, price_drop_events)."""
    store.executescript(LOCAL_SCHEMA)
    add_column_if_missing(store.connection, "listings", "last_seen", "TEXT")
    add_column_if_missing(store.connection, "listings", "dismissed", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(store.connection, "listings", "dismissed_reason", "TEXT")
    # Kategori-generalisering (2026-10-03, se categories.py's docstring):
    # additive kolonner for eksisterende, allerede-oprettede databaser --
    # CREATE TABLE IF NOT EXISTS ovenfor rører ALDRIG en tabel der allerede
    # findes, så disse skal eftermonteres separat, samme mønster som
    # last_seen/dismissed ovenfor da de blev indført.
    add_column_if_missing(
        store.connection, "listings", "category", "TEXT NOT NULL DEFAULT 'stoevsugere'"
    )
    add_column_if_missing(store.connection, "listings", "image_url", "TEXT")
    add_column_if_missing(store.connection, "listings", "attributes_json", "TEXT")
    # Solgt-detektion (2026-10-05, ported fra seng/PASPEAKERS -- se seng's
    # pipeline.py's samme mønster): "misses" tæller op hver gang en allerede-
    # kendt annonce for DENNE kilde+kategori ikke dukker op i en kørsel der
    # selv fandt mindst ét resultat (se bulk-opdateringen efter loopet
    # nedenfor) -- nulstilles til 0 hver gang annoncen genfindes. Frontend/
    # Worker skjuler en annonce når misses >= 3 ELLER last_seen er over 48t
    # gammel (samme to tærskler som seng/PASPEAKERS bruger i produktion).
    # "sold_marker" er en SEPARAT, stærkere kilde-specifik bekræftelse (lige
    # nu kun kleinanzeigen.verify_sold_status(), se main.py) -- sættes
    # ALDRIG af denne generiske funktion, se _INSERT_SQL's kommentar.
    add_column_if_missing(store.connection, "listings", "misses", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(store.connection, "listings", "sold_marker", "INTEGER NOT NULL DEFAULT 0")
    store.connection.execute("UPDATE listings SET last_seen = first_seen WHERE last_seen IS NULL")
    store.connection.commit()

    raw_count = 0
    changed = 0
    price_drop_events: list[dict] = []
    found_keys: set[str] = set()

    try:
        raw_listings = run_with_timeout(
            lambda: fetch_fn(config, dry_run=dry_run),
            timeout_seconds=fetch_timeout_seconds,
            source_name=source_name,
        )
        raw_count = len(raw_listings)
        rates = config["currency"]

        for raw in raw_listings:
            title = raw.get("title", "")
            description = raw.get("description", "")

            listing = category.normalize_listing(
                source=source_name,
                title=title,
                description=description,
                price_amount=raw["price_amount"],
                price_currency=raw["price_currency"],
                url=raw.get("url", ""),
                rates=rates,
                extra=raw.get("extra"),
                origin_country_code=raw.get("origin_country_code"),
                import_costs=config.get("import_costs"),
            )

            # KRITISK RETTELSE (Opus 5-gennemgang, 2026-09-20): dette var
            # tidligere et `continue` FØR normalize_listing() overhovedet
            # kørte -- rækken blev aldrig skrevet, så en allerede-gemt
            # rækkes GAMLE vurdering (fra dengang tilbehørs-mønsteret endnu
            # ikke fangede den) forblev synlig for evigt, uanset senere
            # forbedringer af filtrene. Nu normaliseres OG skrives rækken
            # altid, blot med en direkte "afvis"-dom for tilbehør/udlejning
            # -- så enhver fremtidig regel-ændring automatisk retter
            # allerede-scrapede rækker ved næste besøg, ikke kun nye fund.
            if category.is_accessory_or_rental(
                f"{title} {description}"
            ) or category.is_accessory_title(title):
                verdict = {
                    "score": 0,
                    "score_reasons": [],
                    "vurdering": "afvis",
                    "mangler_info": ["tilbehør/reservedele/udlejning, ikke en hel maskine"],
                    "classification_method": "afvist: tilbehør/udlejning (tekstfilter)",
                    "spoergsmaal_til_saelger": [],
                }
                # R12 (Opus 5-gennemgang af live resultater, 2026-09-20): Workerens
                # "valideret"-felt (se worker/src/index.ts) beregnes UDELUKKENDE fra
                # model_key/klasse_kilde/dust_class -- felter der stadig kom fra
                # normalize_listing() ovenfor og derfor IKKE blev påvirket af dette
                # afvis-verdict. Konkret fund: "Sicherheitsfiltersack für Attix
                # 30-0H PC" matchede Attix-modellen (kompatibilitets-omtale, ikke
                # selve maskinen) og blev derfor vist som "✓ valideret" i
                # frontend'en, selvom det er en reservedelsannonce. Nulstil
                # model-/klassefelterne her, så en bekræftet tilbehørsannonce
                # aldrig kan tælle som en valideret maskine-observation.
                listing = {
                    **listing,
                    "model_key": None,
                    "brand": None,
                    "model_label": None,
                    "dust_class": "ingen (L/ukendt)",
                    "klasse_kilde": None,
                    "container_l": None,
                }
            else:
                verdict = category.classify(listing, config)

            # Auktionskilder (klaravik/auktionshuset/retrade) leverer AKTUELT
            # BUD, ikke en fast pris -- buddet kan stige frem til auktionens
            # slut, så "køb nu" (som antager prisen er endelig/accepteret)
            # ville være misvisende. Nedgraderes til "se nærmere" med en
            # eksplicit note, samme forsigtighedsprincip som PASPEAKERS'
            # ebay.py bruger for eBay-auktioner.
            is_auction = bool((raw.get("extra") or {}).get("is_auction"))
            if is_auction and verdict["vurdering"] == "køb nu":
                verdict = {
                    **verdict,
                    "vurdering": "se nærmere",
                    "mangler_info": [
                        *verdict["mangler_info"],
                        "aktuelt bud, ikke fast pris -- kan stige frem til auktionens slut",
                    ],
                    "classification_method": verdict["classification_method"]
                    + " (nedgraderet: auktion)",
                    "spoergsmaal_til_saelger": list(category.seller_questions),
                }

            item_key = make_item_key(
                source_name, listing.get("url"), listing.get("title"), listing.get("price_dkk")
            )
            # Registreret uanset tilbehørs-/auktionsdomme ovenfor -- en
            # annonce der stadig OPTRÆDER i denne kørsel skal aldrig få
            # misses talt op, uanset hvordan den klassificeres.
            found_keys.add(item_key)
            first_seen = datetime.datetime.now(datetime.UTC).isoformat()

            previous_row = store.connection.execute(
                "SELECT price_dkk, vurdering FROM listings WHERE item_key = ?",
                (item_key,),
            ).fetchone()

            payload = {
                "item_key": item_key,
                "source": source_name,
                "category": category.key,
                "title": listing.get("title"),
                "url": listing.get("url"),
                "image_url": raw.get("extra", {}).get("image_url") if raw.get("extra") else None,
                "location": raw.get("extra", {}).get("location") if raw.get("extra") else None,
                "brand": listing.get("brand"),
                "model_key": listing.get("model_key"),
                "model_label": listing.get("model_label"),
                "dust_class": listing.get("dust_class"),
                "klasse_kilde": listing.get("klasse_kilde"),
                "asbestos_approved": _bool_or_unknown_to_text(listing.get("asbestos_approved")),
                "container_l": listing.get("container_l"),
                "battery": 1 if listing.get("battery") else 0,
                "price_dkk": listing.get("price_dkk"),
                "landed_price_dkk": listing.get("landed_price_dkk"),
                "shipping_customs_dkk": listing.get("shipping_customs_dkk"),
                "origin_country": listing.get("origin_country"),
                "filterrensning": listing.get("filterrensning"),
                "flowsensor": _bool_or_unknown_to_text(listing.get("flowsensor")),
                "stikdaase": _bool_or_unknown_to_text(listing.get("stikdaase")),
                "medfoelger": json.dumps(listing.get("medfoelger", []), ensure_ascii=False),
                "score": verdict["score"],
                "vurdering": verdict["vurdering"],
                "classification_method": verdict["classification_method"],
                "mangler_info": json.dumps(verdict["mangler_info"], ensure_ascii=False),
                "spoergsmaal_til_saelger": json.dumps(
                    verdict["spoergsmaal_til_saelger"], ensure_ascii=False
                ),
                # Kategori-specifikke attributter (fx en dørs bredde/højde/
                # brandklasse) -- stoevsugere-kategorien sætter ingen
                # "attributes"-nøgle i listing, så dette er {} for alle
                # eksisterende rækker, uændret adfærd. Se categories.py.
                "attributes_json": json.dumps(listing.get("attributes", {}), ensure_ascii=False),
                "first_seen": first_seen,
                "last_seen": first_seen,
                "raw_json": json.dumps(listing.get("raw", {}), default=str, ensure_ascii=False),
                # Kun brugt ved FØRSTE indsættelse -- se _INSERT_SQL's kommentar.
                "dismissed": 0,
                "dismissed_reason": None,
            }

            is_new_or_changed = store.upsert_if_changed(
                source=source_name,
                item_key=item_key,
                payload=payload,
                target_table=TARGET_TABLE,
                # first_seen/last_seen/raw_json udelades altid (se scraper-core's
                # egen begrundelse i SCRAPING_LESSONS.md: indsamlings-metadata,
                # ikke selve indholdet).
                hash_payload={
                    k: v
                    for k, v in payload.items()
                    if k
                    not in ("first_seen", "last_seen", "raw_json", "dismissed", "dismissed_reason")
                },
            )
            if not is_new_or_changed:
                store.connection.execute(
                    "UPDATE listings SET last_seen = ?, misses = 0 WHERE item_key = ?",
                    (first_seen, item_key),
                )
                store.connection.commit()
                store.enqueue_update(
                    TARGET_TABLE, {"item_key": item_key, "last_seen": first_seen, "misses": 0}
                )
                continue

            store.connection.execute(_INSERT_SQL, payload)
            store.connection.commit()
            changed += 1

            old_price = previous_row["price_dkk"] if previous_row is not None else None
            new_price = payload["price_dkk"]
            if old_price is not None and new_price is not None and new_price < old_price:
                price_drop_events.append(
                    {
                        "item_key": item_key,
                        "old_price_dkk": old_price,
                        "new_price_dkk": new_price,
                        "pct_change": round((new_price - old_price) / old_price * 100, 1),
                        "old_vurdering": previous_row["vurdering"],
                        "new_vurdering": verdict["vurdering"],
                        "observed_at": first_seen,
                    }
                )

        # Solgt-detektion, 2. halvdel (se misses-kommentaren ovenfor): tæl op
        # for enhver EKSISTERENDE række for netop denne kilde+kategori der
        # ikke optrådte i found_keys -- men KUN når denne kørsel selv fandt
        # mindst ét resultat. Uden det guard ville en enkelt bot-wall-/
        # 0-resultat-kørsel (se fx kleinanzeigen.py's/jyskauktion.py's egne
        # bot-wall-håndtering) fejlagtigt markere HELE kildens beholdning som
        # forsvundet på én gang -- samme faldgrube seng-projektets
        # "found_keys_by_target"-mønster blev bygget til at undgå.
        if found_keys:
            placeholders = ",".join("?" for _ in found_keys)
            store.connection.execute(
                f"UPDATE listings SET misses = misses + 1 "
                f"WHERE source = ? AND category = ? AND item_key NOT IN ({placeholders})",
                (source_name, category.key, *found_keys),
            )
            store.connection.commit()
            newly_missed = store.connection.execute(
                f"SELECT item_key, misses FROM listings "
                f"WHERE source = ? AND category = ? AND item_key NOT IN ({placeholders})",
                (source_name, category.key, *found_keys),
            ).fetchall()
            for row in newly_missed:
                store.enqueue_update(
                    TARGET_TABLE, {"item_key": row["item_key"], "misses": row["misses"]}
                )

        logger.info("%s: %d raw, %d new/changed", source_name, raw_count, changed)
    except SourceTimeoutError:
        pass
    except Exception:
        logger.exception("%s: source failed, skipping - other sources unaffected", source_name)

    return raw_count, changed, price_drop_events
