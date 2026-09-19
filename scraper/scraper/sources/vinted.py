"""Vinted.dk: anonym cookie-priming + ét offentligt catalog-API-kald pr.
søgeterm. Intet login nødvendigt. Ported fra PLAGG's personal-shopper/sources/
vinted.py -- samme cookie-priming/bot-wall-mekanik, men omskrevet til denne
boilerplates fetch(config, dry_run) -> list[dict]-kontrakt (title/description/
price_amount/price_currency/url/origin_country_code/extra), i stedet for
PLAGG's egen {item_id, size, price, ...}-form.

KRITISK, LÆS FØR DU STOLER FOR MEGET PÅ DENNE KILDE: Vinted er en tøj-/
livsstils-markedsplads. Det er UBEKRÆFTET om industrielle H/M-klasse
byggestøvsugere overhovedet findes der i nævneværdigt omfang -- inkluderet
fordi brugeren selv nævnte platformen og den er billig at polle (intet login,
lavt scraping-besvær), IKKE fordi der er dokumenteret markedsdækning. Se
testresultater/smoke-test i README for faktisk observeret volumen.

Fragt er IKKE tilgængelig anonymt (samme fund som PLAGG) -- origin_country_code
sættes derfor til None for alle Vinted-fund (ingen sælger-land-opslag i v1),
hvilket normalize.py's compute_landed_price_dkk behandler som "ingen
import-omkostninger" (samme fallback som en bekræftet EU-sælger).

Fejler ALDRIG hele scriptet: bot-wall/parsefejl logges og giver blot en tom
liste (eller springer det enkelte hit over).
"""

import logging
import random
import time
from urllib.parse import quote

from scraper_core.pricing import parse_price

logger = logging.getLogger("vacuum.vinted")

BASE_URL = "https://www.vinted.dk/"
SEARCH_URL_TMPL = (
    "https://www.vinted.dk/api/v2/catalog/items?search_text={query}&per_page={per_page}&page=1"
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_PRIMING_USER_AGENTS = [
    USER_AGENT,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]
_PRIMING_MAX_ATTEMPTS = 3

BOT_WALL_TEXT_MARKERS = [
    "bekræft at du er et menneske",
    "unormal trafik",
    "adgang nægtet",
    "for mange forespørgsler",
    "captcha",
    "access denied",
    "datadome",
    "are you a robot",
    "human verification",
]


def _build_search_url(term: str, per_page: int) -> str:
    return SEARCH_URL_TMPL.format(query=quote(term), per_page=per_page)


def _is_json_response(resp) -> bool:
    ctype = (resp.headers.get("content-type") or "").lower()
    return "json" in ctype


def _looks_like_bot_wall(resp) -> bool:
    try:
        if resp.status_code in (401, 403, 429):
            return True
    except Exception:
        pass
    if not _is_json_response(resp):
        return True
    try:
        return any(marker in resp.text.lower() for marker in BOT_WALL_TEXT_MARKERS)
    except Exception:
        return False


def _prime_session(timeout: int, max_attempts: int = _PRIMING_MAX_ATTEMPTS):
    import requests

    for attempt in range(max_attempts):
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": _PRIMING_USER_AGENTS[attempt % len(_PRIMING_USER_AGENTS)],
                "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
            }
        )
        try:
            resp = session.get(BASE_URL, timeout=timeout)
        except Exception:
            logger.exception(
                "Vinted: netvaerksfejl under cookie-priming (forsoeg %d/%d)",
                attempt + 1,
                max_attempts,
            )
            resp = None

        if resp is not None and resp.status_code == 200 and session.cookies.get("anon_id"):
            return session

        if attempt < max_attempts - 1:
            time.sleep(random.uniform(2, 5) * (attempt + 1))

    logger.warning(
        "Vinted: cookie-priming fejlede efter %d forsoeg, springer kilden over", max_attempts
    )
    return None


def _hit_to_raw_listing(hit: dict, term: str) -> dict | None:
    if hit.get("is_visible") is False:
        return None

    price_obj = hit.get("price") or {}
    amount_raw = price_obj.get("amount")
    if amount_raw is None:
        return None
    price = parse_price(amount_raw, unit="major", decimal_style="dot")
    if price is None:
        return None

    url = hit.get("url")
    if not url:
        return None

    return {
        "title": hit.get("title") or "",
        "description": "",
        "price_amount": round(price, 2),
        "price_currency": (price_obj.get("currency_code") or "DKK"),
        "url": url,
        # Ikke tilgaengelig anonymt (se modulets docstring) -- behandlet som
        # "ingen import-omkostninger" af normalize.compute_landed_price_dkk.
        "origin_country_code": None,
        "extra": {
            "search_term": term,
            "brand": hit.get("brand_title"),
            "condition": hit.get("status"),
        },
    }


def fetch(config: dict, dry_run: bool = False) -> list[dict]:
    try:
        import requests  # noqa: F401
    except ImportError:
        logger.warning("Vinted: 'requests' er ikke installeret, springer kilden over")
        return []

    vt_cfg = config.get("vinted", {})
    per_page = vt_cfg.get("max_results_per_term", 20)
    timeout = vt_cfg.get("timeout_s", 20)
    min_delay = vt_cfg.get("min_delay_s", 5)
    max_delay = vt_cfg.get("max_delay_s", 15)

    search_terms = config["search_terms"]["primary"] + config["search_terms"].get("secondary", [])
    if not search_terms:
        return []

    raw_listings = []
    try:
        session = _prime_session(timeout)
        if session is None:
            return []

        for term in search_terms:
            try:
                url = _build_search_url(term, per_page)
                logger.info("Vinted: soeger '%s' -> catalog/items", term)
                resp = session.get(url, timeout=timeout, headers={"Accept": "application/json"})

                if _looks_like_bot_wall(resp):
                    logger.warning(
                        "Vinted: bot-wall for '%s' (status=%s), springer resten af koerslen over",
                        term,
                        getattr(resp, "status_code", "?"),
                    )
                    break

                if resp.status_code != 200:
                    logger.warning(
                        "Vinted: uventet status %s for '%s', springer denne term over",
                        resp.status_code,
                        term,
                    )
                    continue

                data = resp.json()
                hits = data.get("items") or []
                for hit in hits:
                    try:
                        listing = _hit_to_raw_listing(hit, term)
                    except Exception:
                        logger.exception("Vinted: kunne ikke parse et hit, springer over")
                        continue
                    if listing is not None:
                        raw_listings.append(listing)

                logger.info("Vinted: '%s' -> %d hits", term, len(hits))
                time.sleep(random.uniform(min_delay, max_delay))
            except Exception:
                logger.exception("Vinted: fejl under haandtering af '%s', springer over", term)
                continue
    except Exception:
        logger.exception("Vinted: kilden fejlede helt, springer kilden over for denne koersel")
        return []

    return raw_listings
