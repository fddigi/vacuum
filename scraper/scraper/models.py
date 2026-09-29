"""Model-database for sikkerhedsstøvsugere (støvklasse H/M).

Kilde: brugerens agent-spec (whitelist/blacklist/referencebilag, sektion 2.1-2.8),
udvidet 2026-09-28 med brugerens egen "stovsuger-modeloversigt.md" (kælderrenovering,
Slotsherrensvej) -- en langt mere kildebelagt gennemgang (fabrikant-datablade/manualer
citeret direkte) af hvilke H-modeller der reelt er asbestgodkendt. Al metadata
(dust_class, container_l, price_new_dkk, asbestos_approved) er transskriberet fra den
kilde der har stærkest dokumentation for netop den model -- se hver entrys "note".

Disambiguerings-princip (samme som PASPEAKERS' normalize.py:MODEL_PATTERNS):
mere specifikke mønstre before generiske, extract_model() i normalize.py
returnerer FØRSTE match i WHITELIST -- rækkefølgen her er derfor selve
disambigueringen for modeller med overlappende tal (fx "Attix 33-2H" vs
"Attix 33-2M").

asbestos_approved-generalisering -- RETTET 2026-09-28 (bruger-beslutning efter
krydstjek mod stovsuger-modeloversigt.md): den oprindelige spec antog at ALLE
Nilfisk/Kärcher/Festool/Flex/Starmix H-maskiner er asbestgodkendt. Brugerens egen,
langt mere grundige gennemgang (fabrikant-datablade citeret direkte, ikke
forhandlertekst) bekræfter dette kun for:
  - Nilfisk: specifikke Attix-modeller med "Asbest"/IC/PC i navnet (varenr.
    107412183 m.fl., "Dust class M and H certification including Asbestos")
  - Flex: VCE 44 H AC ("inkl. Asbest" på fabrikantens datablad)
Kärcher, Festool og Starmix er DERIMOD IKKE bekræftet som brand-brede godkendelser --
modeloversigten placerer netop disse tre mærkers H-modeller i kategori C ("H-klasse,
men asbest forbudt eller gråzone"). Blanket-defaulten er derfor indsnævret til kun
Nilfisk+Flex. Enkelte specifikke modeller med eksplicit "Asbest" i selve produktnavnet
(fx Starmix ISC H-1225 Asbest) beholder asbestos_approved=True via en EKSPLICIT
override på netop den entry, ikke via brand-default. For brands specen aldrig nævnte
i denne sammenhæng (Protool, Metabo, Eibenstock, Numatic, Ermator, Dustcontrol, Ruwac,
Bosch, Milwaukee, Makita, Fein, Mirka, Ronda, Bona, Bygma) er asbestos_approved None
("ukendt") medmindre en specifik note angiver andet -- dette ER en antagelse lagt
oven på kildernes tekst, og bør kunne overskrives af brugeren.

priority_stars -- NYT FELT (2026-09-28): brugerens stovsuger-modeloversigt.md,
afsnit 3, grupperer modeller efter dom i A/B/C/D/E/F/G. Brugeren har bedt om at A/B/C
(de tre kategorier der faktisk er H-klasse og relevante for et asbestjob) prioriteres
i overblikket -- 3=A (asbestgodkendt MED sikkerhedspose, bedste kategori), 2=B (asbest
tilladt, ingen sikkerhedspose), 1=C (H-klasse, men asbest forbudt/gråzone), 0=ikke i
denne kuraterede liste (upåvirket, almindelig H/M-model). Bruges til søgeprioritering
(config.yaml) og en "★"-badge i frontend'en (se worker/src/index.ts' "prioritet"-felt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Brands den oprindelige spec generaliserede som asbestgodkendt for deres H-klasse-
# maskiner (sektion 2.1) -- INDSNÆVRET 2026-09-28, se modulets docstring ovenfor for
# hvorfor Kärcher/Festool/Starmix er fjernet fra denne blanket-default.
_ASBESTOS_APPROVED_H_BRANDS = frozenset({"Nilfisk", "Flex"})


@dataclass(frozen=True)
class ModelEntry:
    key: str
    pattern: re.Pattern
    brand: str
    label: str
    dust_class: str  # "H" eller "M"
    container_l: float | None = None
    price_new_dkk_low: float | None = None
    price_new_dkk_high: float | None = None
    asbestos_approved: bool | None = None  # None = ukendt/ikke oplyst af kilderne
    battery: bool = False  # batterimaskine -- spec: "kun som sekundært fund"
    priority_stars: int = 0  # 0-3, se modulets docstring ("priority_stars")
    note: str = ""

    def __post_init__(self):
        if self.asbestos_approved is None and self.dust_class == "H":
            if self.brand in _ASBESTOS_APPROVED_H_BRANDS:
                object.__setattr__(self, "asbestos_approved", True)


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# Stavefejl-tolerant Attix-præfiks (Opus 5-fund, 2026-09-20, live-data
# 2026-09-19/20): "Atto"/"Attixx"/"Attik" set i rigtige DBA-titler
# ("Nilfisk Atto 33 2H PC", "Nilfisk Alto attik 9 ..."). Brugt i BÅDE
# whitelist-mønstrene nedenfor OG HARD_REJECT_PATTERNS' "Attix uden
# klassebogstav"-mønster -- de to skal blive ved med at bruge samme
# fragment, ellers falder en stavefejlet L-klasse-annonce (fx "Atto 30 21")
# igennem begge net.
_ATTIX = r"att(?:ix|ixx|o|ik)"


# ---------------------------------------------------------------------------
# WHITELIST -- H-klasse (primær) og M-klasse (kun de eksplicit spec-godkendte
# modeller i sektion 2.7, "kun hvis asbest kan udelukkes").
# ---------------------------------------------------------------------------
MODEL_WHITELIST: list[ModelEntry] = [
    # --- H-klasse, kompakt 18-35 l (spec-tabel 2.2) ---
    ModelEntry(
        "metabo_asa30h_pc",
        _p(r"\bmetabo\b.{0,20}\basa[\s-]*30[\s-]*h[\s-]*pc\b"),
        "Metabo",
        "ASA 30 H PC",
        "H",
        30,
        2349,
        2349,
        asbestos_approved=False,
        priority_stars=1,
        note="Nypris korrigeret til 2.349 kr. efter brugerens egen research "
        "(2026-09-20) -- specens egen tabel havde ikke et præcist tal for "
        "denne model. Brugeren fremhæver den som 'billigst forsvarligt' "
        "H-klasse-fund. NB: 'PC'-suffikset er her 'PressClean' -- MANUEL "
        "rensning ifølge brugeren, ikke automatisk. Dette står i modsætning "
        "til spec-scoringens generelle antagelse om at 'PC' indikerer "
        "automatisk/semiautomatisk rens (se normalize.py's "
        "FILTER_CLEANING_PATTERN) -- uafklaret om dette er en generel "
        "unøjagtighed i specen eller specifikt for Metabo. Ikke rettet i "
        "selve scorings-logikken endnu, da 'PC' bruges bredt på tværs af "
        "andre (Nilfisk-)modeller hvor det kan betyde noget andet. "
        "asbestos_approved=False tilføjet 2026-09-28: stovsuger-modeloversigt.md "
        "citerer Metabos egen manual: 'Es dürfen keine asbesthaltigen Stäube "
        "aufgesaugt werden' -- gælder hele AS/ASA-serien.",
    ),
    ModelEntry(
        "metabo_asr35h_acp",
        _p(r"\bmetabo\b.{0,20}\basr[\s-]*35[\s-]*h[\s-]*acp\b"),
        "Metabo",
        "ASR 35 H ACP",
        "H",
        35,
        asbestos_approved=False,
        priority_stars=1,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C): 'Forbudt -- "
        "samme serie' som ASA 30 H PC.",
    ),
    ModelEntry(
        "nilfisk_aero_26_2h_pc",
        _p(r"\baero[\s-]*26[\s-]*2h[\s-]*pc\b"),
        "Nilfisk",
        "AERO 26-2H PC",
        "H",
        25,
        3100,
        3500,
        priority_stars=2,
    ),
    ModelEntry(
        "nilfisk_aero_21h",
        _p(r"\baero[\s-]*21[\s-]*h\b"),
        "Nilfisk",
        "AERO 21 H",
        "H",
        21,
        priority_stars=2,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3B): samme serie "
        "og samme begrænsning som AERO 26-2H PC (asbest tilladt jf. manual, men "
        "ingen safety filter bag i reservedelslisten).",
    ),
    ModelEntry(
        "starmix_energetic_1420h",
        _p(r"\benergetic[\s-]*1420[\s-]*h\b"),
        "Starmix",
        "Energetic 1420 H",
        "H",
        20,
        3500,
        4000,
        priority_stars=1,
    ),
    ModelEntry(
        "starmix_energetic_sx110080h",
        _p(r"\bsx[\s-]*-?\s*110080[\s-]*h\b"),
        "Starmix",
        "Energetic SX-110080 H",
        "H",
        None,
        priority_stars=1,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C): 'Til "
        "kvartsstøv. Asbeststatus ikke dokumenteret.'",
    ),
    ModelEntry(
        "starmix_isc_1418_mini_h",
        _p(r"\bisc[\s-]*1418[\s-]*mini[\s-]*h\b"),
        "Starmix",
        "ISC 1418 MINI H",
        "H",
        18,
        4400,
        4400,
    ),
    # Tjekkes FØR det korte "isc h 1425"-fallback nedenfor ville alligevel ikke
    # kollidere (forskelligt tal), men holdt eksplicit adskilt for klarhed.
    ModelEntry(
        "starmix_isc_h_1425",
        _p(r"\bisc[\s-]*h?[\s-]*1425\b"),
        "Starmix",
        'ISC "H" 1425 (Asbest)',
        "H",
        25,
        4400,
        6500,
        asbestos_approved=True,
        note="Spec nævner eksplicit 'Asbest' i navnet -- asbestgodkendt. "
        "asbestos_approved gjort EKSPLICIT 2026-09-28 (ikke længere via "
        "Starmix-brand-default, se modulets docstring) -- navnets egen "
        "'Asbest'-mærkning er uafhængig af brand-spørgsmålet.",
    ),
    ModelEntry(
        "starmix_isc_h1225_asbest",
        _p(r"\bisc[\s-]*h?[\s-]*-?\s*1225\b"),
        "Starmix",
        "ISC H-1225 Asbest",
        "H",
        25,
        asbestos_approved=True,
        priority_stars=3,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3A): 'Eneste "
        "ISC-variant, hvor manualen tillader asbest.' Adskil fra ISC H-1625 "
        "(nedenfor), som manualen eksplicit lister som en ANDEN maskine.",
    ),
    ModelEntry(
        "flex_vce33h_ac",
        _p(r"\bvce[\s-]*33[\s-]*h[\s-]*ac\b"),
        "Flex",
        "VCE 33 H AC",
        "H",
        30,
        5800,
        5800,
    ),
    # Attix 33-2H: matcher BÅDE "IC" (i produktion) og "PC" (udgået, sektion
    # 2.5) suffiks-varianter under samme model_key -- begge er samme grund-
    # maskine (30 l, H-klasse), kun filterrens-suffiks adskiller dem, og det
    # opsamles separat af normalize.py's tekst-baserede feature-scan.
    ModelEntry(
        "nilfisk_attix_33_2h",
        _p(rf"\b{_ATTIX}[\s-]*33[\s-]*2h\b"),
        "Nilfisk",
        "Attix 33-2H (IC/PC)",
        "H",
        30,
        6100,
        8500,
        priority_stars=3,
        note="stovsuger-modeloversigt.md (2026-09-28), afsnit 3A: 'ASBES' i "
        "produktnavnet, varenr. 107412183, 'Dust class M and H certification "
        "including Asbestos' -- brugerens top-anbefaling for nykøb (4.999 kr.).",
    ),
    ModelEntry(
        "nilfisk_attix_30_0h",
        _p(rf"\b{_ATTIX}[\s-]*30[\s-]*0h\b"),
        "Nilfisk",
        "Attix 30-0H PC",
        "H",
        30,
        6000,
        8000,
        priority_stars=3,
    ),
    ModelEntry(
        "nilfisk_attix_30_2h",
        _p(rf"\b{_ATTIX}[\s-]*30[\s-]*2h\b"),
        "Nilfisk",
        "Attix 30-2H PC",
        "H",
        30,
        6000,
        8500,
        priority_stars=3,
    ),
    ModelEntry(
        "eibenstock_dss35hip",
        _p(r"\bdss[\s-]*35[\s-]*hip\b"),
        "Eibenstock",
        "DSS 35 HIP",
        "H",
        35,
        6000,
        6000,
    ),
    ModelEntry(
        "karcher_nt30_1_ap_te_h",
        _p(r"\bnt[\s-]*30\s*/?\s*1[\s-]*ap[\s-]*te[\s-]*h\b"),
        "Kärcher",
        "NT 30/1 Ap Te H",
        "H",
        30,
        6000,
        6000,
    ),
    ModelEntry(
        "karcher_nt30_1_tact_te_h",
        _p(r"\bnt[\s-]*30\s*/?\s*1[\s-]*tact[\s-]*te[\s-]*h\b"),
        "Kärcher",
        "NT 30/1 Tact Te H",
        "H",
        30,
        6250,
        9300,
    ),
    ModelEntry(
        "bosch_gas35h_afc",
        _p(r"\bgas[\s-]*35[\s-]*h[\s-]*afc\b"),
        "Bosch",
        "GAS 35 H AFC",
        "H",
        35,
        7200,
        9400,
        priority_stars=1,
    ),
    ModelEntry(
        "festool_cth26ei",
        _p(r"\bcth[\s-]*26[\s-]*ei\b"),
        "Festool",
        "CTH 26 EI",
        "H",
        26,
        8300,
        10000,
        priority_stars=1,
    ),
    ModelEntry(
        "hilti_vc40h_x",
        _p(r"\bvc[\s-]*40[\s-]*h[\s-]*-?\s*x\b"),
        "Hilti",
        "VC 40H-X",
        "H",
        30,
        asbestos_approved=False,
        priority_stars=1,
        note="Spec: 'flag: ikke asbestgodkendt' -- Hilti fraskriver sig eksplicit asbest.",
    ),
    # --- H-klasse, store 40-75 l (spec-tabel 2.3) ---
    ModelEntry(
        "starmix_ipulse_isp1635h_basic",
        _p(r"\bipulse[\s-]*isp[\s-]*1635[\s-]*h\b(?!.{0,15}safe)"),
        "Starmix",
        "iPulse ISP 1635 H Basic",
        "H",
        35,
        6200,
        6400,
    ),
    ModelEntry(
        "flex_vce44h_ac",
        _p(r"\bvce[\s-]*44[\s-]*h[\s-]*ac\b"),
        "Flex",
        "VCE 44 H AC",
        "H",
        42,
        6800,
        13400,
        priority_stars=3,
        note="stovsuger-modeloversigt.md (2026-09-28), afsnit 3A: 'inkl. Asbest' "
        "på fabrikantens datablad.",
    ),
    ModelEntry(
        "starmix_ipulse_safe1635ew_h",
        _p(r"\bipulse[\s-]*safe[\s-]*1635[\s-]*ew[\s-]*h\b"),
        "Starmix",
        "iPulse Safe 1635 EW H",
        "H",
        35,
        8100,
        8100,
    ),
    ModelEntry(
        "starmix_ipulse_h1635_safe_plus",
        _p(r"\bipulse[\s-]*h[\s-]*-?\s*1635[\s-]*safe(?:[\s-]*plus)?\b"),
        "Starmix",
        "iPulse H-1635 Safe Plus",
        "H",
        35,
        priority_stars=1,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C): 'Uafklaret "
        "-- markedsføres til asbest, men kun af forhandlere. Få det på skrift "
        "fra importøren før køb.' Adskilt model_key fra 'iPulse Safe 1635 EW H' "
        "ovenfor -- forskellig ordstilling i navnet, ikke bekræftet samme maskine.",
    ),
    ModelEntry(
        "festool_cth48e",
        _p(r"\bcth[\s-]*48[\s-]*e\b(?!i)"),
        "Festool",
        "CTH 48 E",
        "H",
        48,
        priority_stars=1,
        note="Samme modelnavn optræder i spec både som 'i produktion' (tabel 2.3) "
        "og udgået m. artikelnr. 576908 (tabel 2.5) -- én model_key her.",
    ),
    ModelEntry(
        "nilfisk_attix_50_0h",
        _p(rf"\b{_ATTIX}[\s-]*50[\s-]*0h\b"),
        "Nilfisk",
        "Attix 50-0H PC",
        "H",
        47,
        12500,
        16750,
        priority_stars=3,
    ),
    ModelEntry(
        "nilfisk_attix_751_0h",
        _p(rf"\b{_ATTIX}[\s-]*751[\s-]*0h\b"),
        "Nilfisk",
        "Attix 751-0H (Asbest)",
        "H",
        70,
        priority_stars=3,
        note="Spec nævner eksplicit 'Asbest' i navnet.",
    ),
    ModelEntry(
        "nilfisk_attix_965",
        _p(rf"\b{_ATTIX}[\s-]*965[\s-]*0?[\s-]*[hm]\b"),
        "Nilfisk",
        "Attix 965-0H/M SD XC",
        "H",
        70,
        priority_stars=3,
        note="Spec skriver '0H/M' -- dual-klasse-betegnelse, matchet som H her.",
    ),
    ModelEntry(
        "nilfisk_ivb965_sd_xc",
        _p(r"\bivb[\s-]*965\b"),
        "Nilfisk",
        "IVB 965 SD XC",
        "H",
        70,
        priority_stars=3,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3A): tysk "
        "navngivning for Attix 965-serien -- samme maskine.",
    ),
    ModelEntry(
        "karcher_nt75_1_tact_me_h",
        _p(r"\bnt[\s-]*75\s*/?\s*1[\s-]*tact[\s-]*me[\s-]*h\b"),
        "Kärcher",
        "NT 75/1 Tact Me H",
        "H",
        75,
    ),
    ModelEntry(
        "ronda_2800h",
        _p(r"\bronda[\s-]*2800[\s-]*h\b"),
        "Ronda",
        "2800 H",
        "H",
        None,
        39000,
        39000,
        note="Ikke i den oprindelige mærke-liste, men i spec-referencetabel 2.3 -- "
        "tilføjet for fuldstændighed.",
    ),
    # KRITISK FUND (Opus 5-gennemgang, 2026-09-20): kun "2800 H" var dækket,
    # men live-data viste ægte fund som "RONDA 80H 25L" og "RONDA 1800H
    # Power" -- Ronda bruger konsekvent H-suffiks for støvklasse H på tværs
    # af hele modelserien. Denne GENERISKE fallback står bevidst EFTER
    # ronda_2800h ovenfor (mere specifik model_key/pris bevares for netop
    # den model), og fanger resten. container_l/pris er ukendt pr. model,
    # så "verificér typeskilt" jf. spec-sektion 2.6.
    ModelEntry(
        "ronda_h_serie",
        _p(r"\bronda\b.{0,15}?\b\d{2,4}\s*-?\s*h\b"),
        "Ronda",
        "H-serie (verificér typeskilt)",
        "H",
        None,
        priority_stars=3,
        note="Generisk Ronda-H-mønster, se kommentar ovenfor -- ikke fra specen "
        "selv. stovsuger-modeloversigt.md (2026-09-28, afsnit 3A) bekræfter "
        "RONDA 200H Power og 80H/80H25 som asbestgodkendt m. sikkerhedspose "
        "(Brøndums datablad) -- dækket generisk af dette mønster.",
    ),
    ModelEntry(
        "bona_dcs25",
        _p(r"\bbona\b.{0,15}\bdcs[\s-]*25\b"),
        "Bona",
        "DCS 25",
        "H",
        16,
        asbestos_approved=True,
        priority_stars=3,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3A): 'Manual "
        "nævner asbest, plastsæk min. 100 µm specificeret.' Intet H/M i selve "
        "modelnavnet, men brand+modelnummer er specifikt nok (samme princip "
        "som ermator_s26/husqvarna_s26 nedenfor).",
    ),
    # --- H-klasse, batteri (spec-tabel 2.4) -- sekundært fund jf. spec ---
    ModelEntry(
        "starmix_isc_1625_mpb_h",
        _p(r"\bisc[\s-]*1625[\s-]*mpb[\s-]*h\b"),
        "Starmix",
        "ISC 1625 MPB H",
        "H",
        25,
        5495,
        5995,
        battery=True,
        note="Nypris korrigeret til 5.495-5.995 kr. efter brugerens egen "
        "research (2026-09-20) -- specens egen tabel 2.4 angav 8.400-10.500 "
        "kr., som brugeren udtrykkeligt har fundet upræcist. Brugeren "
        "bekræfter desuden: automatisk filterrensning, HEPA 14, og "
        "plastsæk der opfylder Arbejdstilsynets asbestkrav.",
    ),
    ModelEntry(
        "starmix_isc_h1625",
        _p(r"\bisc[\s-]*h[\s-]*-?\s*1625\b|\bisc[\s-]*1625[\s-]*h\b"),
        "Starmix",
        "ISC H-1625",
        "H",
        25,
        asbestos_approved=False,
        priority_stars=1,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C): 'Ikke "
        "asbestvarianten -- manualen lister ISC H-1625 og ISC H-1225 Asbest "
        "som to maskiner.' Mønster kræver INGEN 'mpb' mellem 1625 og H, så "
        "kolliderer ikke med ISC 1625 MPB H (batteri-variant) ovenfor.",
    ),
    ModelEntry(
        "starmix_vaccufix_h",
        _p(r"\bvaccufix[\s-]*h\b"),
        "Starmix",
        "Vaccufix H",
        "H",
        6,
        battery=True,
        note="18V Makita-kompatibel, kun oprydning ifølge spec.",
    ),
    # --- H-klasse, udgåede, bekræftet (spec-tabel 2.5) ---
    ModelEntry(
        "karcher_nt35_1_tact_te_h",
        _p(r"\bnt[\s-]*35\s*/?\s*1[\s-]*tact[\s-]*te[\s-]*h\b"),
        "Kärcher",
        "NT 35/1 Tact Te H",
        "H",
        35,
        note="Spec: 'Udløb 2018. Bedste brugtjagt.' RETTET 2026-09-28: "
        "asbestos_approved sat til ukendt (ikke længere True) -- den "
        "oprindelige specs 'Asbestgodkendt'-påstand for denne model er en "
        "brand-niveau-antagelse, som brugerens langt mere kildebelagte "
        "stovsuger-modeloversigt.md IKKE bekræfter (Kärcher NT...H placeres "
        "der i kategori C, 'forbudt eller gråzone', uden model-specifik "
        "dokumentation). Se modulets docstring.",
    ),
    ModelEntry(
        "karcher_nt50_1_tact_te_h",
        _p(r"\bnt[\s-]*50\s*/?\s*1[\s-]*tact[\s-]*te[\s-]*h\b"),
        "Kärcher",
        "NT 50/1 Tact Te H",
        "H",
        50,
    ),
    ModelEntry(
        "festool_cth26e",
        _p(r"\bcth[\s-]*26[\s-]*e\b(?!i)"),
        "Festool",
        "CTH 26 E (576907)",
        "H",
        26,
        priority_stars=1,
    ),
    ModelEntry(
        "nilfisk_attix_995",
        _p(rf"\b{_ATTIX}[\s-]*995[\s-]*0?[\s-]*[hm]\b"),
        "Nilfisk",
        "Attix 995-0H/M SD XC",
        "H",
        70,
        priority_stars=3,
        note="To motorer, XtremeClean, stål.",
    ),
    ModelEntry(
        "nilfisk_attix_44_2h",
        _p(rf"\b{_ATTIX}[\s-]*44[\s-]*2h\b"),
        "Nilfisk",
        "Attix 44-2H IC",
        "H",
        44,
        priority_stars=3,
        note="InfiniClean, tretrins filtrering.",
    ),
    ModelEntry(
        "nilfisk_ivb5h",
        _p(r"\bivb[\s-]*5[\s-]*h\b"),
        "Nilfisk",
        "IVB 5 H",
        "H",
        30,
        priority_stars=3,
        note="Tysk navn for Attix -- samme maskine.",
    ),
    ModelEntry(
        "nilfisk_ivb7h",
        _p(r"\bivb[\s-]*7[\s-]*h\b"),
        "Nilfisk",
        "IVB 7 H",
        "H",
        70,
        priority_stars=3,
        note="Tysk navn for Attix -- samme maskine.",
    ),
    # --- H-klasse, verificér typeskilt (spec-tabel 2.6, lavere tillid) ---
    ModelEntry(
        "protool_vcp260eh",
        _p(r"\bvcp[\s-]*260[\s-]*e[\s-]*-?\s*h\b"),
        "Protool",
        "VCP 260 E-H",
        "H",
        None,
    ),
    ModelEntry(
        "protool_vcp480eh",
        _p(r"\bvcp[\s-]*480[\s-]*e[\s-]*-?\s*h\b"),
        "Protool",
        "VCP 480 E-H",
        "H",
        None,
    ),
    ModelEntry(
        "starmix_gs_h_1232", _p(r"\bgs[\s-]*h[\s-]*-?\s*1232\b"), "Starmix", "GS H-1232", "H", None
    ),
    ModelEntry(
        "starmix_hs_ar_1635_ehp",
        _p(r"\bhs[\s-]*ar[\s-]*-?\s*1635[\s-]*ehp\b"),
        "Starmix",
        "HS AR-1635 EHP",
        "H",
        None,
    ),
    ModelEntry(
        "starmix_ipulse_h1235_asbest",
        _p(r"\bipulse[\s-]*h[\s-]*-?\s*1235\b"),
        "Starmix",
        "iPulse H-1235 Asbest",
        "H",
        None,
        asbestos_approved=True,
        note="Spec nævner eksplicit 'Asbest' i navnet. asbestos_approved gjort "
        "EKSPLICIT 2026-09-28 (ikke længere via Starmix-brand-default, se "
        "modulets docstring).",
    ),
    ModelEntry(
        "bygma_isc_h163_safe",
        _p(r"\bbygma\b.{0,20}\bisc[\s-]*h[\s-]*-?\s*163\b"),
        "Bygma",
        "ISC H-163 Safe",
        "H",
        None,
        priority_stars=1,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C): rebrandet "
        'Starmix. \'Uafklaret -- tjek om typeskiltet bærer "Safe" eller '
        '"ASBEST".\'',
    ),
    ModelEntry(
        "numatic_hz200",
        _p(r"\bhz[\s-]*200\b"),
        "Numatic",
        "HZ200",
        "H",
        None,
        note="'HZ' = Hazardous, jf. spec.",
    ),
    ModelEntry("numatic_hz370", _p(r"\bhz[\s-]*370\b"), "Numatic", "HZ370", "H", None),
    ModelEntry("numatic_hzd750", _p(r"\bhzd[\s-]*750\b"), "Numatic", "HZD750", "H", None),
    ModelEntry("ruwac_na7_26", _p(r"\bna\s*7[\s-]*-?\s*26\b"), "Ruwac", "NA7-26", "H", None),
    ModelEntry(
        "ermator_s26",
        _p(r"\b(?:ermator|husqvarna)\b.{0,20}\bs[\s-]*26\b"),
        "Ermator/Husqvarna",
        "S26",
        "H",
        None,
        note="Samme maskine solgt under begge mærker jf. spec.",
    ),
    ModelEntry("ermator_s36", _p(r"\bermator\b.{0,20}\bs[\s-]*36\b"), "Ermator", "S36", "H", None),
    ModelEntry(
        "dustcontrol_dc_tromb_400h",
        _p(r"\bdc[\s-]*tromb[\s-]*400[\s-]*h\b"),
        "Dustcontrol",
        "DC Tromb 400 H",
        "H",
        None,
    ),
    ModelEntry(
        "nilfisk_attix_550_0h",
        _p(rf"\b{_ATTIX}[\s-]*550[\s-]*0h\b"),
        "Nilfisk",
        "Attix 550-0H",
        "H",
        None,
        priority_stars=3,
    ),
    # Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C: "Kärcher NT ... H |
    # H-klasse | Kun med efterstillet H er en NT H-klasse"). Generisk fallback,
    # samme princip som ronda_h_serie ovenfor -- fanger NT-modeller uden egen
    # specifik whitelist-entry (fx "NT 45/1 Tact Te H", set i live-data men
    # aldrig whitelistet). Placeret SIDST blandt H-entries, så alle specifikke
    # NT-mønstre ovenfor (som allerede returnerer tidligere i loopet) altid
    # vinder først. Samme 25-tegns-afstandstærskel som HARD_REJECT_PATTERNS'
    # "karcher_nt_uden_klassebogstav" bruger til at AFGØRE om et NT-fund har H
    # i nærheden -- de to mønstre er derfor gensidigt udelukkende: alt dette
    # matcher ville ALDRIG være blevet hård-afvist alligevel.
    ModelEntry(
        "karcher_nt_h_serie",
        _p(r"\bnt[\s-]*\d{2,3}\s*/\s*\d\b.{0,25}?\bh\b"),
        "Kärcher",
        "NT-serie H (verificér typeskilt)",
        "H",
        None,
        priority_stars=1,
        note="Generisk NT+H-fallback. asbestos_approved bevidst IKKE sat til "
        "True -- se korrigeret Kärcher-politik i modulets docstring.",
    ),
    # --- M-klasse, kun hvis asbest kan udelukkes (spec-sektion 2.7) ---
    ModelEntry(
        "bosch_gas35m_afc", _p(r"\bgas[\s-]*35[\s-]*m[\s-]*afc\b"), "Bosch", "GAS 35 M AFC", "M"
    ),
    ModelEntry(
        "bosch_gas55m_afc", _p(r"\bgas[\s-]*55[\s-]*m[\s-]*afc\b"), "Bosch", "GAS 55 M AFC", "M"
    ),
    ModelEntry("makita_vc4210m", _p(r"\bvc[\s-]*4210[\s-]*m\b"), "Makita", "VC4210M", "M"),
    ModelEntry(
        "nilfisk_attix_30_2m_pc",
        _p(rf"\b{_ATTIX}[\s-]*30[\s-]*2m[\s-]*pc\b"),
        "Nilfisk",
        "Attix 30-2M PC",
        "M",
    ),
    ModelEntry(
        "nilfisk_attix_33_2m_pc",
        _p(rf"\b{_ATTIX}[\s-]*33[\s-]*2m[\s-]*pc\b"),
        "Nilfisk",
        "Attix 33-2M PC",
        "M",
    ),
    ModelEntry(
        "nilfisk_attix_50_2m_pc",
        _p(rf"\b{_ATTIX}[\s-]*50[\s-]*2m[\s-]*pc\b"),
        "Nilfisk",
        "Attix 50-2M PC",
        "M",
    ),
    ModelEntry(
        "karcher_nt30_1_tact_te_m",
        _p(r"\bnt[\s-]*30\s*/?\s*1[\s-]*tact[\s-]*te[\s-]*m\b"),
        "Kärcher",
        "NT 30/1 Tact Te M",
        "M",
    ),
    ModelEntry(
        "karcher_nt40_1_tact_te_m",
        _p(r"\bnt[\s-]*40\s*/?\s*1[\s-]*tact[\s-]*te[\s-]*m\b"),
        "Kärcher",
        "NT 40/1 Tact Te M",
        "M",
    ),
    ModelEntry("flex_vce33m_ac", _p(r"\bvce[\s-]*33[\s-]*m[\s-]*ac\b"), "Flex", "VCE 33 M AC", "M"),
    ModelEntry(
        "metabo_asr35m_acp", _p(r"\basr[\s-]*35[\s-]*m[\s-]*acp\b"), "Metabo", "ASR 35 M ACP", "M"
    ),
    ModelEntry(
        "metabo_asa30m_pc", _p(r"\basa[\s-]*30[\s-]*m[\s-]*pc\b"), "Metabo", "ASA 30 M PC", "M"
    ),
    ModelEntry("milwaukee_as30mac", _p(r"\bas[\s-]*30[\s-]*mac\b"), "Milwaukee", "AS 30 MAC", "M"),
    ModelEntry("milwaukee_as42mac", _p(r"\bas[\s-]*42[\s-]*mac\b"), "Milwaukee", "AS 42 MAC", "M"),
    ModelEntry("festool_ctm26", _p(r"\bctm[\s-]*26\b"), "Festool", "CTM 26", "M"),
    ModelEntry("festool_ctm36", _p(r"\bctm[\s-]*36\b"), "Festool", "CTM 36", "M"),
    ModelEntry("festool_ctm48", _p(r"\bctm[\s-]*48\b"), "Festool", "CTM 48", "M"),
    ModelEntry(
        "hilti_vc20_um",
        _p(r"\bvc[\s-]*20[\s-]*-?\s*um\b"),
        "Hilti",
        "VC 20-UM",
        "M",
        asbestos_approved=False,
    ),
    ModelEntry(
        "hilti_vc40_um",
        _p(r"\bvc[\s-]*40[\s-]*-?\s*um\b"),
        "Hilti",
        "VC 40-UM",
        "M",
        asbestos_approved=False,
    ),
    ModelEntry(
        "hilti_vc20m_x",
        _p(r"\bvc[\s-]*20[\s-]*m[\s-]*-?\s*x\b"),
        "Hilti",
        "VC 20M-X",
        "M",
        asbestos_approved=False,
    ),
    ModelEntry(
        "hilti_vc40m_x",
        _p(r"\bvc[\s-]*40[\s-]*m[\s-]*-?\s*x\b"),
        "Hilti",
        "VC 40M-X",
        "M",
        asbestos_approved=False,
    ),
    ModelEntry("fein_dustex35mx", _p(r"\bdustex[\s-]*35[\s-]*mx\b"), "Fein", "Dustex 35 MX", "M"),
    ModelEntry("mirka_de1230m", _p(r"\bde[\s-]*1230[\s-]*m\b"), "Mirka", "DE 1230 M", "M"),
    # --- Gråzone, ikke asbestgodkendt (stovsuger-modeloversigt.md, afsnit 3C) ---
    ModelEntry(
        "makita_vc3211h",
        _p(r"\bvc[\s-]*3211[\s-]*h\b"),
        "Makita",
        "VC3211H",
        "H",
        32,
        asbestos_approved=None,
        priority_stars=1,
        note="Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 1+3C): "
        "brugerens TOP-anbefaling ved negative asbestprøver (2.000 kr. brugt, "
        "'bedste værkstedsmaskine', dybeste reservedelsnet i DK). Asbeststatus "
        "'gråzone' -- manualen forbyder ikke, men henviser til myndighederne, "
        "og kræver dekontaminering hos autoriseret institut efter asbestbrug. "
        "Ingen sikkerhedspose. asbestos_approved bevidst None (hverken "
        "godkendt eller forbudt), IKKE False.",
    ),
]

# ---------------------------------------------------------------------------
# HARD REJECT -- kendte fælder (spec BLACKLIST + sektion 2.8). Tjekkes KUN
# hvis intet WHITELIST-mønster matchede (se normalize.py:classify_model) --
# en whitelistet H/M-model skal ALDRIG kunne blive afvist af et bredere
# blacklist-mønster, så rækkefølgen "whitelist først" er selve garantien her,
# ikke negative lookaheads i hvert blacklist-mønster.
# ---------------------------------------------------------------------------
HARD_REJECT_PATTERNS: list[tuple[str, re.Pattern]] = [
    # KRITISK FUND (Opus 5-gennemgang af live data, 2026-09-20): de to
    # oprindelige mønstre herunder dækkede kun "NT 35/1"/"NT 30/1" og
    # missede reelle DBA-fund som "NT 45/1 Tact Te" og "NT 30/1 Wet & Dry"
    # (specen kalder netop NT-uden-H "den mest udbudte maskine overhovedet").
    # Generaliseret til ALLE "NT <tal>/<tal>"-modeller uden et H/M inden for
    # rimelig afstand. Whitelisten tjekkes altid FØRST (se normalize.py), så
    # NT 35/1 Tact Te H, NT 30/1 Ap Te H, NT 75/1 Tact Me H osv. rammes
    # aldrig af dette -- testet eksplicit mod alle whitelistede NT-modeller.
    ("karcher_nt_uden_klassebogstav", _p(r"\bnt[\s-]*\d{2,3}\s*/\s*\d\b(?!.{0,25}\b[hm]\b)")),
    ("karcher_t_serie", _p(r"\bk[äa]rcher\b.{0,15}\bt[\s-]*serien?\b")),
    # KRITISK FUND (live-test 2026-09-19): tidligere version af dette mønster
    # var `\bwd[\s-]*\d` UDEN mærke-kontekst, og ramte fejlagtigt en Nilfisk-
    # annonce ("Nilfisk Atrixx Maxxi WD 7") -- resultatet (afvis) var
    # tilfældigvis korrekt for DEN annonce, men af den forkerte grund, og
    # ville kunne ramme et helt andet mærkes legitime model forkert. Kræver nu
    # eksplicit "kärcher"/"karcher" i nærheden, samme princip som
    # karcher_t_serie ovenfor.
    ("karcher_wd_serie", _p(r"\bk[äa]rcher\b.{0,20}\bwd[\s-]*\d")),
    # KRITISK FUND (Opus 5-gennemgang, 2026-09-20): 44% af al støj i en
    # live-stikprøve var Nilfisk Attix/Alto-modeller UDEN klassebogstav
    # (fx "Attix 50-21", "ATTIX 751-11", "Attix 9 961-01") -- Attix-serien
    # nummereres <størrelse>-<variant>, hvor variantens sidste tegn ER
    # klassen (-0H/-2H = H, -2M = M, mens -01/-11/-21/-51 er L/ingen klasse).
    # Specen blacklister eksplicit "Attix 30-01/-11/-21", men det oprindelige
    # mønster dækkede kun 30-serien. Generaliseret til HELE Attix-familien,
    # inkl. stavefejl-varianter (se _ATTIX). Whitelisten tjekkes altid FØRST,
    # så alle H/M-klassificerede Attix-modeller er beskyttet -- testet
    # eksplicit mod samtlige whitelistede Attix-mønstre ovenfor.
    (
        "nilfisk_attix_uden_klassebogstav",
        _p(rf"\b{_ATTIX}\b(?![\s-]*\d{{1,3}}[\s-]*-?\s*\d?\s*[hm]\b)"),
    ),
    # "Nilfisk Atrixx Maxxi" (L-klasse forbruger-serie, adskilt fra Attix) og
    # bar "Attix/attik 7/8/9" uden noget modelnummer overhovedet (fx "Nilfisk
    # Alto attik 9 våd- og tørstøvsuger") -- ingenting at verificere.
    ("nilfisk_maxxi_wd", _p(r"\bmaxxi\b")),
    ("nilfisk_attix_bar_serie_7_9", _p(rf"\b{_ATTIX}\s*[789]\b")),
    # Kärcher-produktlinjer der IKKE er våd-/tørsugere (højtryksrensere,
    # gulvvaskere, tæpperensere, vinduespudsere, kost/fejemaskiner). 0 hits i
    # de faktiske data pr. 2026-09-20, men billig forsikring før
    # kleinanzeigen.de/blocket.se's bredere Kärcher-sortiment kommer i drift.
    (
        "karcher_ikke_stoevsuger",
        _p(
            r"\bk[äa]rcher\b.{0,25}\b(?:hd|hds|k\s?[2-7]|puzzi|br\s?\d|bd\s?\d|"
            r"sc\s?\d|wv\s?\d|fc\s?\d|km\s?\d)\b"
        ),
    ),
    ("nilfisk_sq650_3m", _p(r"\bsq[\s-]*650[\s-]*3m\b")),
    ("nilfisk_sq690_3m", _p(r"\bsq[\s-]*690[\s-]*3m\b")),
    ("nilfisk_sq691_9m", _p(r"\bsq[\s-]*691[\s-]*9m\b")),
    ("nilfisk_attix_791_2m", _p(rf"\b{_ATTIX}[\s-]*791[\s-]*2m\b")),
    ("nilfisk_vp300", _p(r"\bvp[\s-]*300\b")),
    ("nilfisk_gd930", _p(r"\bgd[\s-]*930\b")),
    ("nilfisk_multi_ii", _p(r"\bmulti[\s-]*ii\b")),
    ("wap_alto_dynamics_840", _p(r"\b(?:wap[\s-]*)?alto\b.{0,10}\bdynamics\b.{0,10}\b840\b")),
    # Festool CT-basen uden L/M/H-klassebetegnelse (CTL/CTM/CTH med tal
    # dækkes allerede af WHITELIST ovenfor og matches ALDRIG hertil, da
    # whitelisten tjekkes først) -- fanger bare-CTL og de klasseløse
    # CT MIDI/CT SYS-varianter.
    ("festool_ctl_generisk", _p(r"\bctl\b")),
    ("festool_ct_midi_sys", _p(r"\bct[\s-]*(?:midi|sys)\b")),
    ("makita_l_serie", _p(r"\b(?:dvc[\s-]*750l|dvc[\s-]*860l|vc[\s-]*3011l)\b")),
    ("dewalt_l_serie", _p(r"\b(?:dc[\s-]*500|dcv[\s-]*582|dcv[\s-]*584l)\b")),
    ("bosch_l_serie", _p(r"\bgas[\s-]*(?:15|25|35)[\s-]*l\b")),
    ("bosch_18v", _p(r"\bgas[\s-]*18v\b")),
    ("fein_turbo", _p(r"\bfein\b.{0,15}\bturbo[\s-]*(?:ii|xl)\b")),
    ("laavkvalitetsmaerker", _p(r"\b(?:arebos|scheppach|powerplus|einhell)\b")),
    # KRITISK FUND (bruger diskvalificerede 10 rigtige DBA-fund manuelt
    # 2026-09-19, alle husholdningsstøvsugere): H/M-klasse er ALTID en stor
    # kabinet-/hjulmaskine med separat slange -- disse produktkategorier kan
    # KATEGORISK aldrig være en sikkerhedsstøvsuger, uanset mærke/pris, så de
    # afvises som en produkttype, ikke et specifikt mærke/model.
    # "askestoevsuger" udvidet fra kun det sammensatte ord (fangede ikke
    # "Aske Støvsuger" i to ord, som var et af de 10 fund) til også at kræve
    # "askepot(te)" (askespand/askebeholder-tilbehør, samme fund).
    ("askestoevsuger", _p(r"\baske[\s-]*(?:st[øo]vsuger|suger)[e]?\b")),
    ("askepotte", _p(r"\baskepot(?:te)?\b")),
    ("haandstoevsuger", _p(r"\bh[åa]ndst[øo]vsuger[e]?\b")),
    ("akkustoevsuger", _p(r"\bakku[\s-]*st[øo]vsuger[e]?\b")),
    ("stavstoevsuger", _p(r"\bstavst[øo]vsuger[e]?\b")),
    ("robotstoevsuger", _p(r"\brobotst[øo]vsuger[e]?\b")),
    ("bilstoevsuger", _p(r"\bbilst[øo]vsuger[e]?\b")),
    ("vinduesstoevsuger", _p(r"\bvindues[\s-]*(?:st[øo]vsuger|suger)[e]?\b")),
    ("lille_stoevsuger", _p(r"\blille\s+st[øo]vsuger\b")),
]

# Svage "bevis" der IKKE alene må tælle som dokumentation for maskinens
# støvklasse (spec: "Disse formuleringer er IKKE bevis for støvklasse").
# Bruges af normalize.py til at afgøre om en UKLASSIFICERET annonce (intet
# whitelist-match) reelt kun sælger sig selv på filter-marketing.
WEAK_EVIDENCE_PATTERN = _p(
    r"\b(hepa(?:\s*1[34])?|99[.,]9[79]\s*%|99[.,]995\s*%|industrist[øo]vsuger|"
    r"byggest[øo]vsuger|professionel|filtrerer\s+fint\s+st[øo]v)\b"
)

# Eksplicit klasse-udsagn i selve annonceteksten ("klasse H", "støvklasse M",
# "Sicherheitssauger Klasse H") -- tæller som klasse_kilde="annoncetekst" når
# intet whitelist-modelmatch findes, men er STADIG svagere end et modelmatch
# (ingen model kan bekræftes, kun sælgers eget udsagn).
EXPLICIT_CLASS_PATTERN = _p(
    r"\b(?:st[øo]vklasse|dust\s*class|klasse|staubklasse)\s*[:\-]?\s*([hm])\b"
)

# Generiske søgetermer fra specen ("H-klasse støvsuger", "sikkerhedsstøvsuger"
# osv.) -- bruges som config.yaml's search_terms.primary/secondary, samlet
# her så de ikke skal duplikeres mellem config og kode.
GENERIC_SEARCH_TERMS = [
    "H-klasse støvsuger",
    "sikkerhedsstøvsuger",
    "asbestsuger",
    "støvklasse H",
    "Sicherheitssauger Klasse H",
    "Asbestsauger",
    "klass H",
]


def model_search_terms() -> list[str]:
    """Ét søgeord pr. whitelistet model (mærke + label), til brug som
    supplerende søgetermer -- se search_terms.py/config.yaml."""
    return sorted({f"{m.brand} {m.label}".split(" (")[0] for m in MODEL_WHITELIST})


def priority_model_keys(min_stars: int = 1) -> list[str]:
    """model_key for alle whitelistede modeller med priority_stars >= min_stars
    -- brugt til at eksponere de samme 3A/3B/3C-prioriterede modeller til
    Worker'en (worker/src/index.ts' "prioritet"-felt) uden at duplikere selve
    kurateringen der (samme princip som config.yaml's kommentar om hvorfor
    search_terms IKKE er kodegenereret: Workeren er TypeScript, ikke Python,
    så en vis duplikering er uundgåelig, men selve listen af NØGLER kan
    genereres herfra og limes ind, i stedet for at vedligeholdes frit i hånden)."""
    return sorted(m.key for m in MODEL_WHITELIST if m.priority_stars >= min_stars)


# KRITISK FUND (live-test 2026-09-19 mod dba.dk): flere reelle Nilfisk
# Attix-annoncer (fx "Attix 751-11", "Attix 965-21 DC XC") blev fejlagtigt
# afvist af weak-evidence-reglen (normalize.WEAK_EVIDENCE_PATTERN), fordi de
# nævner "industristøvsuger" et sted i teksten OG modelnummeret ikke matcher
# nogen af de whitelistede varianter præcist -- selvom mærket ATTIX/NILFISK
# er en kendt sikkerhedsstøvsuger-serie, og der derfor er en reel chance for
# at det bare er en model_key models.py endnu ikke dækker (se sektion 2.6's
# "verificér typeskilt"-liste, som allerede erkender whitelisten ikke er
# udtømmende). Løsning: et kendt mærke nævnt i teksten nedgraderer "kun svag
# evidens" fra AFVIS til SE NÆRMERE (bed om typeskilt) i stedet for et
# automatisk, endeligt afslag -- se normalize.mentions_known_brand() og
# classify.py's brug af den.
KNOWN_BRANDS = frozenset(m.brand.split("/")[0] for m in MODEL_WHITELIST)
