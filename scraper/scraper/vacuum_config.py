"""Loader dette projekts config.yaml (søgetermer, prislofter, scoring, kilder,
import-omkostninger, Playwright-indstillinger).

Holdt separat fra scraper_core.config.Settings med vilje: den delte klasse
dækker kun framework-niveau env-vars (TURSO_*, LOCAL_SQLITE_PATH,
HEALTHCHECK_URL, LOG_LEVEL) fælles for alle projekter på denne boilerplate.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(path: str | Path | None = None) -> dict:
    # VACUUM_CONFIG_PATH lader CI pege på en kilder-deaktiveret fixture (se
    # config.ci-smoke.yaml) uden at røre den rigtige config.yaml -- de rigtige
    # kilder rammer kommercielle markedspladser og må aldrig køre uovervåget
    # mod delte CI-runners ved hvert push/PR.
    env_path = os.environ.get("VACUUM_CONFIG_PATH", DEFAULT_CONFIG_PATH)
    config_path = Path(path) if path else Path(env_path)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
