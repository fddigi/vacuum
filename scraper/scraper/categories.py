"""Kategori-registry for multi-kategori SHV-sourcing (udvidet 2026-10-03).

BAGGRUND: "vacuum" startede som en ren sikkerhedsstøvsuger-scraper, men
projektet er nu omdefineret til at dække sourcing af materialer og udstyr
til HELE SHV-projektet (Slotsherrensvej 139 -- totalrenovering af et
tidligere bageri). Brugerens ord: "Vacuum er et projekt som handler om
sourcing af materialer og udstyr til SHV-projektet." Første udvidelse på
vej: døre (DBA har mange, men ingen mål-filter) og brandvinduer/BD60 samt
genbrugs-byggematerialer generelt.

ARKITEKTUR-PRINCIP: hver kategori er en selvstændig varegruppe med sin egen
normalize/classify-logik (helt forskellige attributter -- en dørs bredde/
højde/brandklasse har intet med en støvsugers støvklasse/asbestgodkendelse
at gøre), men ALLE kategorier deler den samme scraping-/sync-infrastruktur
(sources/*.py, scraper-core's LocalStore/TursoClient/sync, pipeline.py's
run_source()). Dette modul er dispatch-laget: en `Category` samler de
funktioner pipeline.py skal kalde, så run_source() aldrig selv behøver vide
hvilken kategori den kører for en given kilde-kørsel.

Kun ÉN kategori er reelt implementeret endnu (stoevsugere, uændret logik --
dette er en RENT ADDITIV omlægning, ingen adfærdsændring for eksisterende
data). En ny kategori (fx døre) tilføjes ved at:
  1. Skrive dens egen normalize_listing()/classify() (ny fil, samme
     kontrakt som scraper.normalize/scraper.classify, men med
     kategoriens egne attributter i stedet for dust_class/container_l/...).
  2. Registrere den som en ny `Category`-instans i CATEGORIES nedenfor.
  3. Give den sin egen søgetermer-sektion (se search_terms.py/config.yaml).
  4. Tilføje et faneblad i frontend/index.html.
Ingen ændring i pipeline.py, main.py, Worker'en eller databaseskemaet er
nødvendig for dette -- se pipeline.py's `category`/`attributes_json`/
`image_url`-kolonner, som allerede er generiske nok til at bære en ny
kategoris data.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import classify as _vacuum_classify
from . import doere_classify as _doere_classify
from . import doere_normalize as _doere_normalize
from . import normalize as _vacuum_normalize


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    # Samme kontrakter som scraper.normalize.normalize_listing/is_accessory_*
    # og scraper.classify.classify -- se de respektive moduler for den fulde
    # signatur. Enhver fremtidig kategori SKAL implementere disse tre.
    normalize_listing: Callable[..., dict]
    classify: Callable[[dict, dict], dict]
    is_accessory_or_rental: Callable[[str], bool]
    is_accessory_title: Callable[[str], bool]
    # Brugt af pipeline.py's auktions-nedgraderingslogik (aktuelt bud, ikke
    # fast pris) -- kategoriens egne standardspørgsmål, ikke nødvendigvis
    # støvsugerens (en dør har andre ting at spørge ind til end et typeskilt).
    seller_questions: list[str]
    # Hver kategori har sin EGEN config.yaml-fil (se main.py's load pr.
    # kategori) -- stoevsugere-kategorien er fuldt optaget af
    # prislofter/filterestimat/M-klasse-logik, som intet har med en dørs
    # bredde/højde at gøre. Delte infrastruktur-felter (currency,
    # import_costs, playwright) duplikeres bevidst pr. fil, samme princip
    # som config.yaml's søgetermer duplikerer models.py's whitelist.
    config_path: str
    # Dynamisk, webapp-redigerbar søgeterm-liste via Turso (se
    # search_terms.py) -- kun relevant for kategorier der rent faktisk
    # bruger den delte search_terms-tabel. doere-kategorien bruger v1
    # kun statiske termer fra sin egen config-fil.
    uses_dynamic_search_terms: bool = True


CATEGORIES: dict[str, Category] = {
    "stoevsugere": Category(
        key="stoevsugere",
        label="Sikkerhedsstøvsugere",
        normalize_listing=_vacuum_normalize.normalize_listing,
        classify=_vacuum_classify.classify,
        is_accessory_or_rental=_vacuum_normalize.is_accessory_or_rental,
        is_accessory_title=_vacuum_normalize.is_accessory_title,
        seller_questions=list(_vacuum_classify.SELLER_QUESTIONS),
        config_path="config.yaml",
    ),
    # Første udvidelses-kategori (2026-10-04) -- se doere_normalize.py/
    # doere_classify.py's docstrings. Første kilde: genbyg.dk (struktureret
    # mål pr. kort); dba.dk kan tilføjes senere via samme kategori ved kun
    # at udvide dens søgetermer, ingen ny kategori-kode nødvendig.
    "doere": Category(
        key="doere",
        label="Døre",
        normalize_listing=_doere_normalize.normalize_listing,
        classify=_doere_classify.classify,
        is_accessory_or_rental=_doere_normalize.is_accessory_or_rental,
        is_accessory_title=_doere_normalize.is_accessory_title,
        seller_questions=list(_doere_classify.SELLER_QUESTIONS),
        config_path="config.doere.yaml",
        uses_dynamic_search_terms=False,
    ),
}

DEFAULT_CATEGORY = CATEGORIES["stoevsugere"]
