"""Entry point for vacuum-scraperen (brugte H/M-klasse sikkerhedsstøvsugere).

Kilder: dba.dk, guloggratis.dk, kleinanzeigen.de, blocket.se, klaravik.dk,
auktionshuset.dk, retrade.eu, jyskauktion.dk (tilføjet 2026-10-04, jysk
konkurs-/overskudsauktionshus, fundet af brugeren selv -- se
sources/jyskauktion.py), facebook.com/marketplace (genoptaget 2026-09-30, se
sources/facebook.py's docstring for den fulde risikoafvejning -- kræver
login, modsat alle øvrige kilder). vinted.dk er deaktiveret (dødt API, se
config.yaml). eBay Browse API og Traderas API er BEVIDST UDELADT i v1
(kræver brugerens egen developer-registrering, se README.md).

Run directly with `python -m scraper.main`, via the `scraper-run` console
script, or through the launchd job installed by `make install-launchd`.
"""

from __future__ import annotations

import argparse
import fcntl
import logging
import sys
from pathlib import Path

from scraper_core.config import Settings, get_settings
from scraper_core.healthcheck import ping_fail, ping_success
from scraper_core.local_db import LocalStore
from scraper_core.logging_setup import configure_logging
from scraper_core.sync import sync_pending
from scraper_core.turso_client import TursoClient

from .categories import CATEGORIES, Category
from .pipeline import SYNC_PROTECTED_COLUMNS, TURSO_SCHEMA, run_source
from .price_history import sync_price_history_to_turso
from .schema_utils import add_column_if_missing
from .search_terms import config_for_source, load_search_terms
from .source_cadence import SOURCE_STATE_SCHEMA, mark_source_run, should_run_source
from .sources import (
    auktionshuset,
    blocket,
    dba,
    facebook,
    genbyg,
    guloggratis,
    jk_genbrugscenter,
    jyskauktion,
    klaravik,
    kleinanzeigen,
    retrade,
    skave_nedbrydning,
    vinted,
)
from .vacuum_config import load_config

logger = logging.getLogger(__name__)

SOURCE_MODULES = {
    "dba": dba,
    "guloggratis": guloggratis,
    "kleinanzeigen": kleinanzeigen,
    "blocket": blocket,
    "vinted": vinted,
    "klaravik": klaravik,
    "auktionshuset": auktionshuset,
    "retrade": retrade,
    "facebook": facebook,
    "jyskauktion": jyskauktion,
    "genbyg": genbyg,
    "jk_genbrugscenter": jk_genbrugscenter,
    "skave_nedbrydning": skave_nedbrydning,
}

# KRITISK FUND (live-test 2026-09-20): efter search_terms-reseed-fixet
# (se search_terms.py) begyndte kilder reelt at søge alle ~53 termer fra
# config.yaml i stedet for kun 3 -- en fuld dba.dk-kørsel tog da over 300s
# (standard-watchdog-budgettet), hvilket fik watchdog'en til at give op
# midt i kørslen. Værre end blot en langsom kørsel: se run_with_timeout()'s
# egen docstring -- den underliggende fetch()-tråd bliver IKKE dræbt, den
# kører videre i baggrunden og når muligvis at blive færdig, men dens
# resultat bliver ALDRIG synkroniseret, fordi main() allerede har givet op
# og logget "0 raw" på det tidspunkt. Konkret observeret: en hel
# dba.dk-kørsel med 53 termer fuldførte reelt i baggrunden, men 0 rækker
# blev synkroniseret til Turso. Alle Playwright-baserede kilder (som alle
# har samme min_delay_s/max_delay_s-throttling pr. side/term) udvidet til
# 900s -- samme værdi PASPEAKERS/kleinanzeigen allerede brugte for et
# tilsvarende voksende søgefelt. Vinted (API-baseret, ingen sidenavigation
# pr. term) beholder standard-budgettet.
SOURCE_TIMEOUT_OVERRIDES = {
    "dba": 900,
    "guloggratis": 900,
    "kleinanzeigen": 900,
    "blocket": 900,
    "klaravik": 900,
    "auktionshuset": 900,
    "retrade": 900,
    "facebook": 900,
    "jyskauktion": 900,
    # 30s obligatorisk crawl-delay pr. side (robots.txt-krav, se
    # sources/skave_nedbrydning.py's docstring) -- 7 kategorier, op til ~110
    # sider i alt hvis max_pages_total ikke begrænser det, kan derfor tage
    # markant længere end de øvrige kilder.
    "skave_nedbrydning": 3600,
}

# To uafhængige triggere (launchd-schedule + evt. fremtidig "Kør nu"-knap) kan
# starte en kørsel næsten samtidig -- denne fil-lås forhindrer at de to racer
# på samme lokale SQLite-fil.
LOCK_PATH = Path("data/.scraper.lock")


def run(force_source: str | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logger.warning(
            "Another scraper run is already in progress (lock held on %s) - skipping this run",
            LOCK_PATH,
        )
        lock_file.close()
        return 0

    try:
        return _run_locked(settings, force_source=force_source)
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def _enabled_sources_for(category_config: dict, force_source: str | None) -> list[str]:
    enabled = [name for name, on in category_config.get("sources", {}).items() if on]
    if force_source is not None:
        # --source filtrerer PR. KATEGORI: en kildenavn hører kun til de
        # kategorier der rent faktisk har den i deres egen sources:-liste
        # (fx "genbyg" findes kun i config.doere.yaml) -- en kørsel med
        # --source genbyg skal derfor IKKE forsøge at køre den under
        # stoevsugere-kategorien, hvor den slet ikke er konfigureret.
        enabled = [name for name in enabled if name == force_source]
    return enabled


def _verify_kleinanzeigen_sold(store: LocalStore, category: Category, config: dict) -> None:
    """Solgt-verifikation (2026-10-05, se kleinanzeigen.verify_sold_status()'s
    docstring for det MÅLTE fund bag dette): kleinanzeigen.de's søgeresultat-
    kort viser aldrig et "solgt/reserveret"-mærke, men en direkte genbesøgt
    annonce-URL gør, via et <h1>-præfiks. Kaldes derfor HER, efter den
    normale fetch()-baserede source-loop, kun for rækker der allerede er
    mistænkt forsvundet (misses >= 1) eller er over 24t gamle -- IKKE for
    hele beholdningen hver kørsel, både for at begrænse antallet af ekstra
    sidebesøg og fordi en helt frisk/aktiv annonce ikke har brug for
    bekræftelse. Grænsen på 40 pr. kørsel holder den ekstra køretid på linje
    med kleinanzeigen's eksisterende 900s-timeout-budget (se
    SOURCE_TIMEOUT_OVERRIDES)."""
    candidates = store.connection.execute(
        "SELECT item_key, url FROM listings "
        "WHERE source = 'kleinanzeigen' AND category = ? AND dismissed = 0 AND sold_marker = 0 "
        "AND (misses >= 1 OR (julianday('now') - julianday(last_seen)) * 24 >= 24) "
        "ORDER BY last_seen ASC LIMIT 40",
        (category.key,),
    ).fetchall()
    if not candidates:
        return

    url_to_key = {row["url"]: row["item_key"] for row in candidates}
    results = kleinanzeigen.verify_sold_status(list(url_to_key), config)
    confirmed_sold = 0
    confirmed_active = 0
    for url, is_sold in results.items():
        item_key = url_to_key[url]
        if is_sold:
            store.connection.execute(
                "UPDATE listings SET sold_marker = 1 WHERE item_key = ?", (item_key,)
            )
            store.enqueue_update("listings", {"item_key": item_key, "sold_marker": 1})
            confirmed_sold += 1
        else:
            # Bekræftet stadig aktiv -- en falsk "forsvundet"-mistanke
            # (fx fordi annoncen var midlertidigt uden for de sider/termer
            # denne kørsel dækkede), rydder derfor miss-tælleren.
            store.connection.execute(
                "UPDATE listings SET misses = 0 WHERE item_key = ?", (item_key,)
            )
            store.enqueue_update("listings", {"item_key": item_key, "misses": 0})
            confirmed_active += 1
    store.connection.commit()
    logger.info(
        "kleinanzeigen solgt-verifikation: %d kandidat(er), %d bekræftet solgt, "
        "%d bekræftet stadig aktiv, %d ikke-verificerbar(e)",
        len(candidates),
        confirmed_sold,
        confirmed_active,
        len(candidates) - len(results),
    )


def _run_category(
    store: LocalStore,
    category: Category,
    turso: TursoClient | None,
    force_source: str | None,
) -> tuple[int, int, list[dict]]:
    """Kører alle (kildespecifikke) fetch()-kald for ÉN kategori. Delt mellem
    Turso- og lokal-only-tilstand (kaldes med turso=None i sidstnævnte)."""
    category_config = load_config(category.config_path)
    min_interval_hours = category_config.get("sources_min_interval_hours", {})
    enabled_sources = _enabled_sources_for(category_config, force_source)

    if category.uses_dynamic_search_terms and turso is not None:
        dynamic_term_pairs = load_search_terms(category_config, turso)
        category_config["search_terms"] = {
            "primary": [term for term, _cat in dynamic_term_pairs],
            "secondary": [],
            # Kildespecifikke supplementer lever KUN i config-filen og
            # seedes aldrig til Turso -- se search_terms.config_for_source().
            "per_source": (category_config.get("search_terms") or {}).get("per_source", {}),
        }

    total_raw = 0
    total_changed = 0
    price_drop_events: list[dict] = []
    for name in enabled_sources:
        module = SOURCE_MODULES.get(name)
        if module is None:
            logger.warning("Unknown source configured: %s, skipping", name)
            continue
        if not should_run_source(
            store.connection, name, min_interval_hours, force=force_source is not None
        ):
            continue
        run_source_kwargs = {}
        if name in SOURCE_TIMEOUT_OVERRIDES:
            run_source_kwargs["fetch_timeout_seconds"] = SOURCE_TIMEOUT_OVERRIDES[name]
        raw_count, changed, events = run_source(
            store,
            name,
            module.fetch,
            config_for_source(category_config, name),
            category=category,
            **run_source_kwargs,
        )
        mark_source_run(store.connection, name)
        total_raw += raw_count
        total_changed += changed
        price_drop_events.extend(events)

    if "kleinanzeigen" in enabled_sources:
        try:
            _verify_kleinanzeigen_sold(
                store, category, config_for_source(category_config, "kleinanzeigen")
            )
        except Exception:
            logger.exception(
                "kleinanzeigen solgt-verifikation fejlede, resten af kørslen fortsætter"
            )

    logger.info(
        "kategori %s: %d raw across %d source(s), %d new/changed",
        category.key,
        total_raw,
        len(enabled_sources),
        total_changed,
    )
    return total_raw, total_changed, price_drop_events


def _run_locked(settings: Settings, force_source: str | None = None) -> int:
    # KATEGORI-GENERALISERING (2026-10-03/04, se categories.py's docstring):
    # hver registreret kategori har sin egen config-fil (search terms,
    # sources-liste) og sin egen normalize/classify, men deler al øvrig
    # infrastruktur (LocalStore, Turso-sync, watchdog) via dette fælles loop.
    try:
        with LocalStore(settings.local_sqlite_path) as store:
            store.executescript(SOURCE_STATE_SCHEMA)
            grand_total_raw = 0
            grand_total_changed = 0
            synced = 0

            if settings.turso_configured:
                with TursoClient(settings) as turso:
                    turso.execute(TURSO_SCHEMA)
                    # KRITISK FUND (live-test 2026-10-03, kategori-generaliseringen):
                    # add_column_if_missing() blev hidtil KUN kaldt mod den lokale
                    # SQLite-forbindelse (se pipeline.py's run_source()) -- aldrig mod
                    # Turso direkte. Det "virkede" historisk kun ved et tilfælde:
                    # Worker'ens /api/listings kører sin egen ensureColumn() mod Turso,
                    # og dashboardet besøges typisk ofte nok at den vinder kapløbet før
                    # scraperen næste gang synkroniserer en ny kolonne. Lige efter
                    # deploy af de tre nye kolonner (category/image_url/
                    # attributes_json), UDEN at nogen havde ramt API'et først, fejlede
                    # sync_pending() reelt med "no such column: category" mod den
                    # LIVE Turso-database -- scraperen selv må derfor ALDRIG afhænge
                    # af at noget andet system migrerer dens eget skema. Gjort
                    # selvforsynende her for alle additive kolonner, ikke kun de nye.
                    for column, ddl in (
                        ("last_seen", "TEXT"),
                        ("dismissed", "INTEGER NOT NULL DEFAULT 0"),
                        ("dismissed_reason", "TEXT"),
                        ("category", "TEXT NOT NULL DEFAULT 'stoevsugere'"),
                        ("image_url", "TEXT"),
                        ("attributes_json", "TEXT"),
                        ("misses", "INTEGER NOT NULL DEFAULT 0"),
                        ("sold_marker", "INTEGER NOT NULL DEFAULT 0"),
                    ):
                        add_column_if_missing(turso, "listings", column, ddl)

                    all_price_drop_events = []
                    for category in CATEGORIES.values():
                        raw_count, changed, events = _run_category(
                            store, category, turso, force_source
                        )
                        grand_total_raw += raw_count
                        grand_total_changed += changed
                        all_price_drop_events.extend(events)

                    for _ in range(100):  # 100 * 200 = 20.000 rækker/kørsel-loft
                        batch_synced = sync_pending(
                            store, turso, protected_update_columns=SYNC_PROTECTED_COLUMNS
                        )
                        synced += batch_synced
                        if batch_synced == 0:
                            break

                    sync_price_history_to_turso(turso, all_price_drop_events)
                    if all_price_drop_events:
                        logger.info(
                            "price_history: %d prisfald registreret", len(all_price_drop_events)
                        )

                logger.info(
                    "run complete: %d raw across %d category(ies), %d new/changed, "
                    "%d synced to Turso",
                    grand_total_raw,
                    len(CATEGORIES),
                    grand_total_changed,
                    synced,
                )
            else:
                # Graceful fallback: ingen Turso-konto -> lokal-only mode.
                for category in CATEGORIES.values():
                    raw_count, changed, _events = _run_category(store, category, None, force_source)
                    grand_total_raw += raw_count
                    grand_total_changed += changed

                logger.warning(
                    "TURSO_DATABASE_URL/TURSO_AUTH_TOKEN not set - skipping Turso sync "
                    "(local-only mode). %d new/changed item(s) queued locally.",
                    grand_total_changed,
                )
    except Exception:
        logger.exception("scrape run failed")
        ping_fail(settings.healthcheck_url)
        return 1

    ping_success(settings.healthcheck_url)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        choices=sorted(SOURCE_MODULES),
        help="Run only this one source, ignoring its sources_min_interval_hours cadence limit.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(run(force_source=args.source))
