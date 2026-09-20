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

from . import classify, normalize
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
    raw_json TEXT,
    dismissed INTEGER NOT NULL DEFAULT 0,
    dismissed_reason TEXT
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
INSERT INTO listings (item_key, source, title, url, location, brand, model_key,
    model_label, dust_class, klasse_kilde, asbestos_approved, container_l,
    battery, price_dkk, landed_price_dkk, shipping_customs_dkk, origin_country,
    filterrensning, flowsensor, stikdaase, medfoelger, score, vurdering,
    classification_method, mangler_info, spoergsmaal_til_saelger, first_seen,
    last_seen, raw_json, dismissed, dismissed_reason)
VALUES (:item_key, :source, :title, :url, :location, :brand, :model_key,
    :model_label, :dust_class, :klasse_kilde, :asbestos_approved, :container_l,
    :battery, :price_dkk, :landed_price_dkk, :shipping_customs_dkk, :origin_country,
    :filterrensning, :flowsensor, :stikdaase, :medfoelger, :score, :vurdering,
    :classification_method, :mangler_info, :spoergsmaal_til_saelger, :first_seen,
    :last_seen, :raw_json, :dismissed, :dismissed_reason)
ON CONFLICT(item_key) DO UPDATE SET
    title = excluded.title, url = excluded.url, location = excluded.location,
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
    raw_json = excluded.raw_json, last_seen = excluded.last_seen
    -- dismissed/dismissed_reason er BEVIDST udeladt her, se kommentaren ovenfor.
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
    dry_run: bool = False,
    fetch_timeout_seconds: float = 300,
) -> tuple[int, int, list[dict]]:
    """Kører én kildes fetch() -> normalize -> classify -> upsert_if_changed.
    Isoleret try/except pr. kilde -- én kildes fejl må aldrig vælte de andre.

    Returnerer (raw_count, changed_count, price_drop_events)."""
    store.executescript(LOCAL_SCHEMA)
    add_column_if_missing(store.connection, "listings", "last_seen", "TEXT")
    add_column_if_missing(store.connection, "listings", "dismissed", "INTEGER NOT NULL DEFAULT 0")
    add_column_if_missing(store.connection, "listings", "dismissed_reason", "TEXT")
    store.connection.execute("UPDATE listings SET last_seen = first_seen WHERE last_seen IS NULL")
    store.connection.commit()

    raw_count = 0
    changed = 0
    price_drop_events: list[dict] = []

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

            listing = normalize.normalize_listing(
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
            if normalize.is_accessory_or_rental(
                f"{title} {description}"
            ) or normalize.is_accessory_title(title):
                verdict = {
                    "score": 0,
                    "score_reasons": [],
                    "vurdering": "afvis",
                    "mangler_info": ["tilbehør/reservedele/udlejning, ikke en hel maskine"],
                    "classification_method": "afvist: tilbehør/udlejning (tekstfilter)",
                    "spoergsmaal_til_saelger": [],
                }
            else:
                verdict = classify.classify(listing, config)

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
                    "spoergsmaal_til_saelger": list(classify.SELLER_QUESTIONS),
                }

            item_key = make_item_key(
                source_name, listing.get("url"), listing.get("title"), listing.get("price_dkk")
            )
            first_seen = datetime.datetime.now(datetime.UTC).isoformat()

            previous_row = store.connection.execute(
                "SELECT price_dkk, vurdering FROM listings WHERE item_key = ?",
                (item_key,),
            ).fetchone()

            payload = {
                "item_key": item_key,
                "source": source_name,
                "title": listing.get("title"),
                "url": listing.get("url"),
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
                    "UPDATE listings SET last_seen = ? WHERE item_key = ?",
                    (first_seen, item_key),
                )
                store.connection.commit()
                store.enqueue_update(TARGET_TABLE, {"item_key": item_key, "last_seen": first_seen})
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

        logger.info("%s: %d raw, %d new/changed", source_name, raw_count, changed)
    except SourceTimeoutError:
        pass
    except Exception:
        logger.exception("%s: source failed, skipping - other sources unaffected", source_name)

    return raw_count, changed, price_drop_events
