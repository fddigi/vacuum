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
priority_stars er BEVIDST en anden akse end asbestos_approved: stjernerne siger
"hvor højt skal denne model prioriteres i SØGNINGEN" (kildens egen kategorisering),
asbestos_approved siger "kan asbestgodkendelse bevises for netop den maskine en
annonce beskriver". De to kan divergere -- se nilfisk_attix_33_2h nedenfor.

STOR REVISION 2026-09-29 -- brugerens "stovsuger-modeloversigt2.md" (version 3,
eksplicit selvkorrigerende over for version 1-2; afsnit 9 er dens egen changelog).
Dokumentet er nu den stærkeste kilde og slår version 1-2 (input/stovsuger-
modeloversigt.md, beholdt som historisk dokument, men dens tilbagetrukne påstande
må IKKE genciteres i ny kode). De ændringer der rammer denne fil:

  1. AFSNIT 7A, KRITISK: sætningen "Dust class M and H certification including
     Asbestos" på Nilfisks egen side er SERIETEKST for hele 33 M/H-familien -- den
     står ordret også på siden for ATTIX 33-2M PC (varenr. 107412179), en M-maskine
     der IKKE må bruges til asbest. Version 1-2 brugte den som stærkeste bevis for
     Attix 33-2H's asbestgodkendelse; den beviser intet modelspecifikt. Kun
     VARENAVNET er SKU-specifikt: "ASBES" på 107412183 (PC) og "BG BAU ASBEST" på
     107419012 (en anden, sjældnere IC-SKU end den "almindelige" IC 107412184, som
     ingen sådan mærkning har). Konsekvens: nilfisk_attix_33_2h har nu en EKSPLICIT
     asbestos_approved=None (se inherit_brand_asbestos_default nedenfor).
  2. Afsnit 8 retter støvklasse-tærsklerne (IEC 60335-2-69 Annex AA): L <5 %,
     M <0,5 %, H <0,005 % -- version 1-2's "≤1 %"/"≤0,1 %" var FILTERELEMENTETS
     retention, ikke maskinens gennemtrængning. Ikke kodet her (denne fil lagrer
     kun klassebogstavet), men nævnt så tallene ikke genopstår i en kommentar.
  3. Afsnit 8: TRGS 519 er en tysk teknisk regel UDEN retskraft i Danmark, og den
     tyske asbestmærkning er i vidt omfang FABRIKANTERKLÆRET, ikke tredjeparts-
     certificeret. Asbestegnethed er en Zusatzprüfung oven på H-testen. Det
     underbygger husets i forvejen konservative linje, men gør ikke en
     asbestmærkning værdiløs -- den viser at fabrikanten har testet
     bortskaffelsessystemet.
  4. Tilbagetrukne påstande fra version 1-2 der IKKE må genciteres: AERO'ens
     værktøjsstik begrænset til 1100 W (udokumenteret), Nilfisk som "dokumenteret"
     OEM-producent for Makita/Flex/Eibenstock (kilde var et forum -- nedgraderet
     til hypotese), den gamle kr./l-metode (dobbelttælling), og de gamle
     L/M-procenttærskler (se punkt 2).
  5. Volumen/pris rettet pr. model efter afsnit 7A/7B/7C/12 -- se de enkelte
     entries' noter (Attix 44-2H 44->37 l, Hilti VC 40H-X 30->36 l, iPulse H-1635
     Safe Plus None->35 l, AERO 26-2H's nypris til 12's EAN-spredning).

ÅBENT SPØRGSMÅL efter version 3 (bevidst IKKE afgjort her): punkt 1 undergraver
strengt taget også grundlaget for de ØVRIGE Nilfisk-Attix-H-modellers
asbestos_approved=True, som i dag kommer fra _ASBESTOS_APPROVED_H_BRANDS-defaulten
og ikke fra nogen SKU-specifik mærkning. Version 3 lader dem dog stadig stå i afsnit
7A's tabel ("H-klasse med dokumenteret asbestegnethed og sikkerhedspose"), og
retter eksplicit KUN 33-2H-familien (rettelse 8 og 9). Brand-defaulten er derfor
bevaret uændret her; en bredere nedgradering kræver brugerens beslutning.
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
    # NYT 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A): gør det muligt at
    # sige "asbestos_approved er EKSPLICIT ukendt for netop denne model", hvilket
    # asbestos_approved=None alene IKKE kan udtrykke -- None er også default-
    # værdien, og __post_init__ opgraderer den til True for brands i
    # _ASBESTOS_APPROVED_H_BRANDS. Uden dette flag ville et eksplicit "vi ved det
    # ikke" for en Nilfisk/Flex-H-model stille blive lavet om til et "ja".
    # Sæt til False når kilden aktivt har TRUKKET beviset tilbage for modellen.
    inherit_brand_asbestos_default: bool = True
    note: str = ""

    def __post_init__(self):
        if self.asbestos_approved is None and self.dust_class == "H":
            if self.inherit_brand_asbestos_default and self.brand in _ASBESTOS_APPROVED_H_BRANDS:
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
        2569,
        4269,
        priority_stars=2,
        note="container_l=25 BEKRÆFTET 2026-09-29 (stovsuger-modeloversigt2.md, "
        "afsnit 7B + rettelse 18: 'AERO har 25 L beholder, ikke 26' -- allerede "
        "rettet i en tidligere omgang, ingen ændring nødvendig). Nypris RETTET fra "
        "3.100-3.500 til 2.569-4.269 kr.: afsnit 12 dokumenterer en reel "
        "prisspredning på SAMME EAN for netop denne model ('Tjek EAN, ikke navn'), "
        "hvilket er et bredere og bedre belagt interval end afsnit 7B's enkeltstal "
        "(3.300 ny / 2.400 brugt), som det indeholder. Konsekvens: 70%-porten i "
        "classify.py regnes nu mod 2.569 kr. (= 1.798 kr.), ikke 3.100 kr. Det "
        "flugter med dokumentets egen korrigerede brugtregel (afsnit 8: spread "
        "skal overstige filter + poser + mindst 1.000 kr. risikomargin, og 'med "
        "den er AERO brugt til 2.400 kr. stadig ikke værd at tage'). NB: "
        "version 1-2's påstand om at AERO'ens værktøjsstik er begrænset til 1100 W "
        "er TRUKKET TILBAGE som udokumenteret (rettelse 10) og må ikke genciteres; "
        "den er aldrig blevet kodet i denne fil. Sikkerhedspose findes derimod "
        "reelt ikke til AERO (107413549 lister den ikke som kompatibel), hvilket "
        "er hele grunden til kategori B / priority_stars=2.",
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
    ModelEntry(
        "baier_bss608h",
        _p(r"\bbss[\s-]*608[\s-]*h\b"),
        "Baier",
        "BSS 608H",
        "H",
        30,
        7436,
        7436,
        asbestos_approved=None,
        priority_stars=2,
        note="Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 5 + 7A + 11) -- "
        "første Baier-model i whitelisten. asbestos_approved BEVIDST None og IKKE "
        "True, selvom modellen står i afsnit 7A, hvis overskrift lyder 'H-klasse "
        "med dokumenteret asbestegnethed OG sikkerhedspose': dokumentet citerer "
        "INTET model-specifikt asbestbevis for BSS 608H (til forskel fra Flex VCE "
        "44 H AC's 'inkl. Asbest' på databladet eller Nilfisks SKU-navne), og "
        "modellens EGEN række i netop den tabel har 'Sikkerhedspose: ikke fundet'. "
        "Tabellens kategoriplacering og den citerede evidens modsiger altså "
        "hinanden for denne ene model, og husets konvention (se modulets "
        "docstring) er da ukendt frem for gæt. Samme begrundelse for "
        "priority_stars=2 og ikke 3: det ENE kriterium der adskiller 7A fra 7B er "
        "sikkerhedsposen, og den kan ikke bekræftes her -- modellen opfører sig "
        "reelt som en 7B-model. Data jf. 7A: 30 l, 14,5 kg, 69 dB(A), nypris 7.436 "
        "kr. Afsnit 5 nævner den desuden som LEJEmaskine (PV Udlejning); "
        "dokumentets hovedanbefaling er at leje frem for at købe, så et brugtfund "
        "her er et supplement, ikke en modsætning til afsnit 5. Vægt/dB/luftmængde "
        "lagres ikke (ModelEntry har ingen felter til det), og afsnit 8 advarer "
        "eksplicit mod at sammenligne netop Baiers luftmængdetal på tværs af "
        "kilder (manualens 143 m³/t vs. Carl Ras' 74 l/s = 266 m³/t for SAMME "
        "maskine).",
    ),
    # Attix 33-2H: matcher BÅDE "IC" (i produktion) og "PC" (udgået, sektion
    # 2.5) suffiks-varianter under samme model_key -- begge er samme grund-
    # maskine (30 l, H-klasse), kun filterrens-suffiks adskiller dem, og det
    # opsamles separat af normalize.py's tekst-baserede feature-scan.
    #
    # KRITISK RETTELSE 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A +
    # rettelse 8/9) -- HVORFOR DENNE ENTRY IKKE ER SPLITTET I FLERE model_keys:
    # den SKU-specifikke asbestmærkning ("ASBES" på 107412183, "BG BAU ASBEST"
    # på 107419012) kan ikke udledes af IC/PC-suffikset i en annoncetitel --
    # BÅDE den mærkede 107419012 OG den umærkede 107412184 er "IC". En
    # model_key-opdeling på IC/PC ville derfor flytte præcis den samme forkerte
    # antagelse ét lag ned, med et falsk præg af præcision. Den mærkning der
    # FAKTISK er SKU-specifik, optræder som fritekst i annoncen (varenummeret
    # eller ordene "ASBES"/"BG BAU"), og hører derfor hjemme som et
    # tekst-signal, ikke som en model_key: se normalize.py's
    # ASBESTOS_SKU_MARKING_PATTERN / extract_soft_signals()'s
    # "asbest_sku_maerkning" (samme mekanik som nyt_filter/unused_machine).
    ModelEntry(
        "nilfisk_attix_33_2h",
        _p(rf"\b{_ATTIX}[\s-]*33[\s-]*2h\b"),
        "Nilfisk",
        "Attix 33-2H (IC/PC)",
        "H",
        30,
        4999,
        5150,
        asbestos_approved=None,
        inherit_brand_asbestos_default=False,
        priority_stars=3,
        note="RETTET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A + "
        "rettelse 8/9): asbestos_approved nedgraderet fra True (arvet fra "
        "Nilfisk-brand-defaulten) til EKSPLICIT None. Version 1-2's stærkeste "
        "bevis, 'Dust class M and H certification including Asbestos' på "
        "Nilfisks egen side, er serietekst for hele 33 M/H-familien og står "
        "ORDRET også på ATTIX 33-2M PC (varenr. 107412179) -- en M-maskine der "
        "ikke må bruges til asbest. Det der holder, er SKU-specifikt: 'ASBES' i "
        "varenavnet på 107412183 (PC) og 'BG BAU ASBEST' på 107419012 (IC). Den "
        "'almindelige' IC, 107412184, har INGEN sådan mærkning (rettelse 9: "
        "'ASBES-navnet hører til PC'en, ikke IC'en som blev anbefalet'). Et bart "
        "'Attix 33-2H'-match i en annoncetitel kan ikke skelne de tre SKU'er, og "
        "må derfor ikke præsumeres asbestgodkendt. inherit_brand_asbestos_default"
        "=False er nødvendig for at None IKKE opgraderes til True i __post_init__. "
        "priority_stars BEVARET på 3: afsnit 7A lister stadig modellen i kategori "
        "A (sikkerhedspose 107413549 angives kompatibel med Attix 33-2H IC/PC, "
        "44-2H og VHS 40/42), og stjernerne styrer søgeprioritet, ikke "
        "asbestpåstanden. Nypris rettet fra 6.100-8.500 til 4.999-5.150 kr. jf. "
        "afsnit 7A's egne tal (4.999 IC / 5.150 PC) -- strammer samtidig "
        "70%-af-nypris-porten i classify.py, hvilket er den konservative retning.",
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
        36,
        asbestos_approved=False,
        priority_stars=1,
        note="Spec: 'flag: ikke asbestgodkendt' -- Hilti fraskriver sig eksplicit "
        "asbest (bekræftet 2026-09-29: stovsuger-modeloversigt2.md, afsnit 7C, "
        "'FRASKREVET'). container_l RETTET 30 -> 36 l samme dato efter samme "
        "tabel -- '40' i modelnavnet er ikke beholderstørrelsen.",
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
        note="container_l=35 bekræftet 2026-09-29 (stovsuger-modeloversigt2.md, "
        "afsnit 7C), og asbeststatus fastholdt som 'Uafklaret -- kun "
        "forhandlertekst' (rettelse 20). "
        "Ny 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3C): 'Uafklaret"
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
        "(Brøndums datablad) -- dækket generisk af dette mønster. "
        "GENNEMGÅET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A + "
        "rettelse 17): RONDA 200H Power er 14 l POSE / 16 l beholder, ikke ~30 l "
        "som version 1 antog. container_l er BEVIDST stadig None her -- mønsteret "
        "er generisk og dækker 80H/200H/1800H med hver sin størrelse, så et "
        "enkelt tal ville være forkert for de fleste fund. Afsnit 8 bemærker "
        "desuden at netop RONDA (og Bona) er de eneste modeller hvor "
        "kr./l-tallet hviler på fabrikantens OPGIVNE posevolumen og ikke på "
        "kildens eget 85 %-skøn -- altså de mest pålidelige tal i tabellen. "
        "asbestos_approved arves fortsat som None (Ronda er ikke i "
        "_ASBESTOS_APPROVED_H_BRANDS); det er bevidst konservativt, selvom "
        "afsnit 7A placerer 200H Power i kategori A -- mønsteret matcher også "
        "Ronda-modeller kilden intet siger om.",
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
        37,
        priority_stars=3,
        note="InfiniClean, tretrins filtrering. container_l RETTET 44 -> 37 l "
        "2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A's tabel) -- '44' i "
        "modelnavnet er ikke beholderstørrelsen. Tallet er internt konsistent i "
        "kilden: dens kr./l for almindelig pose (0,98) er præcis 30,80 / (37 × "
        "0,85), samme 85 %-fyldningsformel som resten af tabellen. Afsnit 7A "
        "bekræfter desuden at sikkerhedspose 107413549 er kompatibel med 44-2H.",
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
        "makita_vc3211m",
        _p(r"\bvc[\s-]*3211[\s-]*m\b"),
        "Makita",
        "VC3211M (udgået)",
        "M",
        32,
        note="Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 10 + 11 + "
        "rettelse 21: 'VC3211M er udgået'). Whitelistet som M -- ikke for at "
        "SØGE efter den (M-søgeord er bevidst fjernet, se config.yaml), men "
        "for at en VC3211M-annonce klassificeres korrekt som M i stedet for at "
        "få known_brand_mentioned-fribilletten via 'Makita' + et modelnummer. "
        "Kolliderer ikke med makita_vc3211h ovenfor (forskelligt klassebogstav) "
        "eller med HARD_REJECT's makita_l_serie (VC3211L).",
    ),
    # Attix -2M-mønstrene krævede tidligere alle et efterfølgende "PC".
    # UDVIDET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 10, som opregner
    # præcis "Attix 30-2M / 33-2M / 44-2M / 50-2M" blandt de diskvalificerede
    # M-maskiner): IC-varianterne findes reelt, og en "Attix 33-2M IC"-annonce
    # slap tidligere IGENNEM som dust_class="ukendt" + known_brand_mentioned
    # (altså "se nærmere" uden klasse), fordi HARD_REJECT's "Attix uden
    # klassebogstav"-mønster netop SER klassebogstavet og lader den passere.
    # 44-2M er samtidig tilføjet, da den manglede helt.
    ModelEntry(
        "nilfisk_attix_30_2m",
        _p(rf"\b{_ATTIX}[\s-]*30[\s-]*2m\b"),
        "Nilfisk",
        "Attix 30-2M (PC/IC)",
        "M",
        30,
    ),
    ModelEntry(
        "nilfisk_attix_33_2m",
        _p(rf"\b{_ATTIX}[\s-]*33[\s-]*2m\b"),
        "Nilfisk",
        "Attix 33-2M (PC/IC)",
        "M",
        30,
        note="UDVIDET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 6 + 7A + "
        "10): mønsteret krævede tidligere et efterfølgende 'PC' og ville derfor "
        "IKKE fange 'Attix 33-2M IC' -- netop den maskine afsnit 6 anbefaler som "
        "førstevalg hvis asbestprøverne er NEGATIVE (4.499 kr. ny hos "
        "Billigkoste). Uden matchet endte en 33-2M IC-annonce som dust_class "
        "'ukendt' + known_brand_mentioned, altså 'se nærmere' uden klasse. "
        "model_key omdøbt fra 'nilfisk_attix_33_2m_pc' (ingen andre filer "
        "refererede den; M-nøgler er ikke i worker/src/index.ts' "
        "prioritets-lister). Denne entry er samtidig ANKERET for hele afsnit "
        "7A-rettelsen: det er ATTIX 33-2M PC's egen produktside (varenr. "
        "107412179) der bærer sætningen 'Dust class M and H certification "
        "including Asbestos', og som derved beviser at sætningen er serietekst "
        "og ikke en modelgodkendelse -- se nilfisk_attix_33_2h ovenfor. "
        "asbestos_approved forbliver None (M-klasse: må ALDRIG bruges til "
        "asbest, jf. afsnit 10's egen liste).",
    ),
    ModelEntry(
        "nilfisk_attix_44_2m",
        _p(rf"\b{_ATTIX}[\s-]*44[\s-]*2m\b"),
        "Nilfisk",
        "Attix 44-2M (PC/IC)",
        "M",
        37,
        note="Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 10). "
        "container_l=37 l som for H-søstermodellen Attix 44-2H IC, jf. afsnit "
        "7A -- '44' i navnet er ikke beholderstørrelsen.",
    ),
    ModelEntry(
        "nilfisk_attix_50_2m",
        _p(rf"\b{_ATTIX}[\s-]*50[\s-]*2m\b"),
        "Nilfisk",
        "Attix 50-2M (PC/IC)",
        "M",
        47,
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
        "flex_vce44m_ac",
        _p(r"\bvce[\s-]*44[\s-]*m[\s-]*ac\b"),
        "Flex",
        "VCE 44 M AC",
        "M",
        42,
        note="Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 6 + 10): afsnit "
        "6 nævner den som én af fire realistiske M-maskiner hvis asbestprøverne "
        "er negative, afsnit 10 bekræfter den som M (dvs. IKKE asbest). Manglede "
        "helt -- kun H-varianten (flex_vce44h_ac) og VCE 33 M AC var dækket, så "
        "en VCE 44 M AC-annonce endte som 'ukendt' + known_brand_mentioned. "
        "container_l=42 som H-søstermodellen (afsnit 7A).",
    ),
    ModelEntry(
        "baier_bss607m",
        _p(r"\bbss[\s-]*607[\s-]*m\b"),
        "Baier",
        "BSS 607M",
        "M",
        note="Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 11's "
        "modelkode-dekodning: 'Baier BSS 606L/607M/608H'). Tilføjet sammen med "
        "BSS 608H, fordi Baier nu er i KNOWN_BRANDS -- uden denne entry ville en "
        "BSS 607M-annonce få known_brand_mentioned-fribilletten og ende som "
        "'se nærmere' med ukendt klasse i stedet for korrekt M. container_l "
        "ukendt: dokumentet oplyser kun volumen for 608H.",
    ),
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
        "godkendt eller forbudt), IKKE False. "
        "BEKRÆFTET UÆNDRET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 6 + "
        "7C): 32 l, 2600 W værktøjsstik, 16,9 kg, 72,5 dB(A), status fortsat "
        "'Gråzone -- henviser til myndighederne', med manualens ordlyd citeret "
        "direkte: 'Please check with your local authorities for any regulations "
        "regarding the use of these vacuum cleaners when working with toxic "
        "materials such as Asbestos', plus krav om dekontaminering hos "
        "autoriseret institut efter asbestbrug. Version 3 fastholder desuden "
        "anbefalingen (brugt til 2.000 kr.) -- men KUN hvis asbestprøverne er "
        "negative; ved positive prøver anbefaler afsnit 1/5 leje + autoriseret "
        "firma, ikke køb. Vægt/dB/værktøjsstik-watt lagres ikke (ModelEntry har "
        "ingen felter til det).",
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
    # "vc 3211 l" tilføjet 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 11:
    # "Makita VC3211L/M/H") -- L-varianten af den maskine afsnit 6 anbefaler i
    # H-udgave. Whitelisten tjekkes først, så VC3211H/VC3211M rammes aldrig.
    (
        "makita_l_serie",
        _p(r"\b(?:dvc[\s-]*750l|dvc[\s-]*860l|vc[\s-]*3011l|vc[\s-]*3211[\s-]*l)\b"),
    ),
    # Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 11: "Baier BSS
    # 606L/607M/608H"). Baier kom ind i KNOWN_BRANDS med BSS 608H, og uden
    # denne regel ville L-varianten få known_brand_mentioned-fribilletten.
    ("baier_l_serie", _p(r"\bbss[\s-]*606[\s-]*l\b")),
    # Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 10 "Ingen støvklasse":
    # "RONDA 2000 · RONDA 200 (uden H)", uddybet i rettelse 22: "RONDA 200 uden
    # H findes, men er født uden H-filtertrinnet"). Det negative lookahead er
    # det afgørende: "RONDA 200 H"/"RONDA 200H Power" matcher ronda_h_serie i
    # whitelisten, som alligevel tjekkes FØRST -- lookaheadet er derfor kun et
    # ekstra værn hvis rækkefølgen nogensinde skulle blive brudt.
    ("ronda_200_uden_h", _p(r"\bronda\b.{0,10}?\b(?:200|2000)\b(?![\s-]*h\b)")),
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
#
# RETTET 2026-09-29 (Opus-review af intake/validering): "industristøvsuger"
# og "byggestøvsuger" stod med et afsluttende \b og matchede derfor IKKE den
# danske flertalsform "industristøvsugerE" -- netop den form brugerens eget
# Klaravik-eksempel bruger ("Industristøvsugere Electrostar Starmix IS 2
# styk"). Konsekvens i live-data: annoncen fik weak_evidence_only=False og
# faldt derfor helt ned i "intet identificerbart signal" i stedet for at nå
# nogen af de mildere grene. `\w*` i stedet for `\b` dækker nu ental, flertal
# og bestemt form. Samme rettelse for "professionel/professionelle".
WEAK_EVIDENCE_PATTERN = _p(
    r"\b(hepa(?:\s*1[34])?|99[.,]9[79]\s*%|99[.,]995\s*%|industrist[øo]vsuger\w*|"
    r"byggest[øo]vsuger\w*|professionel\w*|filtrerer\s+fint\s+st[øo]v)\b"
)

# ---------------------------------------------------------------------------
# NYT 2026-09-29 (Opus-review af intake/validering, bestilt af brugeren:
# "løsn kravet om kendt mærke uden modelnummer ... byg vores egen
# datavalidering"). Tre nye, uafhængige tekst-signaler der tilsammen erstatter
# den tidligere ENE binære port (known_brand_mentioned skal have et
# modelnummer-agtigt tal, se normalize.has_model_token) med en rangordnet
# stige. Alle tre er målt mod 808 RIGTIGE annoncetitler (707 live-rækker fra
# Turso + 101 friske fund fra brede probe-søgninger mod klaravik/auktionshuset/
# dba/retrade) -- se classify.py's _kandidat_signal() for tallene.
#
# VIGTIG PRÆMIS FOR ALLE TRE: INGEN kilde leverer en beskrivelse. Samtlige
# otte sources/*.py sætter `"description": ""` -- hele klassifikationen hviler
# på TITLEN alene. Derfor er tekst-tunge metoder (spec-tæthed, watt/vægt,
# flow/filterklasse-opremsning) målt til at være uanvendelige her, mens korte,
# titel-bærende signaler (klassebogstav, kategori-substantiv) bærer næsten al
# information. Skulle en kilde senere begynde at levere beskrivelser, bliver
# de tunge metoder først da relevante at genoverveje.
# ---------------------------------------------------------------------------

# Kategori-substantivet "det her er en professionel våd-/tørsuger, ikke en
# husholdningsstøvsuger" -- flersproget (da/sv/de), fordi live-data viste at
# WEAK_EVIDENCE_PATTERN kun dækkede dansk: otte rigtige tyske og svenske
# annoncer ("Bosch Asbest-Sauger Industriestaubsauger", "Nilfisk
# industridammsugare med slang", "Werkstattsauger Starmix ISP iPulse ARH-1635
# Staubklasse H") havde INTET signal overhovedet efter husets mønstre, alene
# fordi ordene var tyske/svenske. Bevidst UDEN det bare "støvsuger"/
# "dammsugare": målt på de samme data giver det bare kategoriord 38 fund hvoraf
# ~3 er relevante (resten er "Bosch dammsugare rosa med teleskoprör"-støj),
# mens industri-formerne giver 23 fund hvoraf ~10 er reelle kandidater.
INDUSTRIAL_CATEGORY_PATTERN = _p(
    r"\b(industrist[øo]vsuger\w*|byggest[øo]vsuger\w*|industridammsugar\w*|"
    r"byggdammsugar\w*|industriesauger\w*|industriestaubsauger\w*|"
    r"bau(?:stellen)?sauger\w*|handwerkssauger\w*|werkstattsauger\w*|"
    r"nass[\s-]*(?:und\s*)?trocken\w*|"
    r"v[åa]d[\s/-]*(?:og\s*)?t[øo]r(?:st[øo]vsuger|suger)\w*|"
    r"v[åa]t[\s/-]*(?:och\s*)?torrdammsugar\w*)\b"
)

# NÆR-DEFINITORISK for støvklasse H: en maskine der markedsføres som
# asbestsuger/sikkerhedssuger PÅSTÅR i sig selv H-klasse (asbest kræver H).
# Det er et kvalitativt stærkere udsagn end INDUSTRIAL_CATEGORY_PATTERN
# ovenfor, og adskilt fra ASBESTOS_APPROVED_TEXT_PATTERN i normalize.py, som
# handler om GODKENDELSE ("asbestgodkendt", "TRGS 519"), ikke om hvad slags
# maskine der sælges.
#
# Konkret fund der motiverede mønsteret: "asbestsuger"/"Asbestsauger" er to af
# vores SYV egne primære søgeord -- vi søgte altså aktivt efter dem, fandt dem
# (3 live-rækker: 'Asbestsauger' 1.119 kr., 'Bosch Asbest-Sauger
# Industriestaubsauger' 2.798 kr., 'Asbest Sauger Sicherheitssauger H'
# 3.730 kr.) og afviste dem derefter selv som "intet identificerbart signal",
# fordi ingen af dem havde et modelnummer. Det er en lukket sløjfe, ikke et
# filter.
#
# Det bare ord "asbest" er BEVIDST IKKE med -- se den lange begrundelse over
# normalize.ASBESTOS_SKU_MARKING_PATTERN: "asbest" alene dækker også det stik
# modsatte (maskinen HAR kørt asbest). Her kræves det sammensat med selve
# maskin-substantivet.
SAFETY_VACUUM_PATTERN = _p(
    r"\b(sikkerhedsst[øo]vsuger\w*|sikkerhedssuger\w*|sicherheitssauger\w*|"
    r"s[äa]kerhetsdammsugar\w*|asbest[\s-]*sauger\w*|asbest[\s-]*s[uv]ger\w*|"
    r"asbest[\s-]*dammsugar\w*|h[\s-]*sauger\w*)\b"
)

# "Handler annoncen overhovedet om en støvsuger?" -- bruges KUN som anker for
# klassebogstav-signalet nedenfor (se normalize.has_class_letter_signal), ikke
# som selvstændig evidens. Uden ankeret er et fritstående "H"/"M" nær
# værdiløst: målt på de 808 titler gav det rå mønster `\b\d{2,4}\s*-?\s*[HM]\b`
# alene 30 fund med kun 14 reelle (47 %), hvor stort set al støj var TYSKE
# DÆKANNONCER ("205/55R16 91H", "225/50 R17 98H" -- H er dækkets
# hastighedsindeks), plus "24H" (timer), "126 H-Kennzeichen" (tysk veteranplade)
# og "Blackheart BH 100 H" (et guitarforstærker-HOVED). Med ankeret forsvandt
# samtlige disse.
VACUUM_DOMAIN_PATTERN = _p(
    r"\b(st[øo]vsuger\w*|st[øo]vsugere\w*|dammsugar\w*|damsugar\w*|sauger\w*|"
    r"staubsauger\w*|vacuum|suger\w*|sugare\b|stoftavskiljar\w*|absaugmobil\w*|"
    r"sugmaskin\w*)\b"
)

# Eksplicit klasse-udsagn i selve annonceteksten ("klasse H", "støvklasse M",
# "Sicherheitssauger Klasse H") -- tæller som klasse_kilde="annoncetekst" når
# intet whitelist-modelmatch findes, men er STADIG svagere end et modelmatch
# (ingen model kan bekræftes, kun sælgers eget udsagn).
EXPLICIT_CLASS_PATTERN = _p(
    r"\b(?:st[øo]vklasse|dust\s*class|klasse|staubklasse)\s*[:\-]?\s*([hm])\b"
)

# Den OMVENDTE ordstilling -- bogstavet FØRST -- som mønsteret ovenfor ikke
# kan matche ("H-klasse", "H-KLASSE", "H Klasse", "H-klass", "M-klasse").
# NYT 2026-09-29 (Opus-review): målt på 808 rigtige annoncetitler fandt den
# 10 annoncer, og ALLE TI var ægte H/M-maskiner -- 'RONDA 40 HEPA H-KLASSE',
# 'NUMATIC Rygstøvsuger RHB150NX H-klasse', 'Festool CTH 26 dammsugare
# (H-klass)', 'Flex-industristøversuger VCE44-AC H-klasse' (500 kr.),
# 'Starmix industristøvsuger – M-klasse', 'Nilfisk Attix 7 Nass-Trockensauger
# H-Klasse Gefahrstoffe' m.fl. Ingen af dem havde nogen klasse i dag.
#
# HOLDT ADSKILT fra EXPLICIT_CLASS_PATTERN og IKKE bare tilføjet som en gren:
# "<bogstav>-Klasse" er også den tyske BILserie-betegnelse. I dette korpus
# optrådte A/B/C/E/G/S/V-Klasse (Mercedes) men aldrig M-Klasse -- den findes
# dog (Mercedes ML), og et H-Kennzeichen-lignende sammenfald er kun et
# tidsspørgsmål. Derfor håndhæver normalize.classify_model() et
# støvsuger-domæne-anker på netop denne gren, præcis som
# has_class_letter_signal() gør. Se dens kald for koblingen.
EXPLICIT_CLASS_SUFFIX_PATTERN = _p(r"(?<![\w-])([hm])\s*[-\s]\s*(?:st[øo]v)?klass(?:e|en)?\b")

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
