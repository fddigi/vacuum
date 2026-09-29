"""Kritisk test af model-genkendelse mod specens egne 'kendte fælder'
(sektion 2.8) og blacklist -- disse SKAL fejle synligt hvis whitelist/
blacklist-rækkefølgen nogensinde ombyttes ved en fremtidig redigering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.normalize import (
    classify_model,
    extract_soft_signals,
    has_class_letter_signal,
    has_model_token,
    is_accessory_or_rental,
    is_accessory_title,
    to_dkk,
)


def test_to_dkk_supports_nok():
    """Regression -- Opus-review 2026-09-29: retrade.eu noterer norske
    auktions-lots i NOK, som to_dkk() tidligere ikke kendte (raise
    ValueError, ville have væltet hele kildens kørsel, se retrade.py)."""
    rates = {"eur_dkk": 7.46, "sek_dkk": 0.70, "nok_dkk": 0.64, "usd_dkk": 6.90}
    assert to_dkk(1000, "NOK", rates) == 640.0


def test_whitelist_h_models_matched_correctly():
    cases = {
        # RETTET 2026-09-28 (stovsuger-modeloversigt.md): Kärcher og Festool er
        # fjernet fra models.py's asbestos-brand-blanket-default -- se
        # models.py's docstring. Begge forventer nu None (ukendt), ikke True.
        "Kärcher NT 35/1 Tact Te H - god stand": ("karcher_nt35_1_tact_te_h", "H", None),
        # RETTET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A): forventede
        # tidligere True. Nilfisks "Dust class M and H certification including
        # Asbestos" er serietekst (står også på ATTIX 33-2M PC, 107412179) og
        # beviser intet modelspecifikt -- kun varenavnene "ASBES" (107412183)
        # og "BG BAU ASBEST" (107419012) er SKU-specifikke, og de kan ikke
        # udledes af et bart "Attix 33-2H"-match. Se models.py's entry.
        "Nilfisk Attix 33-2H IC pæn": ("nilfisk_attix_33_2h", "H", None),
        "Festool CTH 26 EI byggestøvsuger": ("festool_cth26ei", "H", None),
        "Hilti VC 40H-X byggestøvsuger": ("hilti_vc40h_x", "H", False),
    }
    for text, (expected_key, expected_class, expected_asbestos) in cases.items():
        result = classify_model(text)
        assert result["model_key"] == expected_key, text
        assert result["dust_class"] == expected_class, text
        assert result["asbestos_approved"] is expected_asbestos, text
        assert result["hard_reject"] is False, text


def test_whitelist_m_models_matched_correctly():
    result = classify_model("Festool CTM 26 sælges pænt")
    assert result["model_key"] == "festool_ctm26"
    assert result["dust_class"] == "M"
    assert result["hard_reject"] is False


def test_known_traps_from_spec_section_2_8_are_hard_rejected():
    """Spec-sektion 2.8: modeller der LIGNER en gyldig maskine, men er det ikke."""
    traps = [
        "Alto/Nilfisk SQ 650-3M sælges",
        "Alto/Nilfisk SQ 690-3M/B",
        "Alto/Nilfisk SQ 691-9M/B",
        "Wap Alto Dynamics 840-M/B1",
        "Nilfisk Attix 791-2M/B pæn stand",
        "Kärcher NT 35/1 Tact Te sælges billigt",  # UDEN H -- den mest udbudte L-maskine
        "Kärcher NT 30/1 Tact sælges",
        "Festool CTL 26 til salg",
        "Dustcontrol DC 1800 blæser",  # nævnt som "M" i spec, men IKKE i vores M-whitelist
        "Makita DVC750L",
        "DeWalt DCV584L",
        "Nilfisk VP300 HEPA filter",
        "Nilfisk GD930",
        "Nilfisk Multi II",
        "Fein Turbo II gammel",
        "Fein Turbo XL",
        # RETTET 2026-09-29 (egen gennemgang af live-data efter kandidat-
        # stigen): "FLEX VCE 33 L MC industristøvsuger" slap igennem som "se
        # nærmere" -- L er en eksplicit klassebogstav i Flex' egen
        # navngivning, ikke en ukendt specifikation.
        "FLEX VCE 33 L MC industristøvsuger",
        "Flex VCE 26 L MC",
    ]
    for text in traps:
        result = classify_model(text)
        assert result["hard_reject"] is True or result["dust_class"] == "ukendt", (
            f"{text!r} blev fejlagtigt godkendt: {result}"
        )
        # De eksplicit blacklistede (ikke bare "ukendt") skal være hard_reject=True
        if (
            "DC 1800" not in text
        ):  # ikke på blacklisten, kun ikke på whitelisten -- se kommentar nedenfor
            assert result["hard_reject"] is True, f"{text!r} skulle være hard_reject: {result}"


def test_dustcontrol_dc1800_is_unknown_not_approved():
    """DC 1800 er spec-sektion 2.8's eksempel på en M-klasse-fælde, men er IKKE
    i vores M-whitelist (kun 'kendte, spec-godkendte' M-modeller er godkendt) --
    resultatet skal være 'ukendt', IKKE et falsk whitelist-match, og bør ALDRIG
    kunne blive 'køb nu' i classify.py."""
    result = classify_model("Dustcontrol DC 1800 blæser")
    assert result["model_key"] is None
    assert result["dust_class"] == "ukendt"


def test_hilti_m_series_flagged_not_asbestos_approved():
    for text in ["Hilti VC 20-UM", "Hilti VC 40-UM", "Hilti VC 20M-X", "Hilti VC 40M-X"]:
        result = classify_model(text)
        assert result["dust_class"] == "M", text
        assert result["asbestos_approved"] is False, text


def test_whitelist_checked_before_blacklist_disambiguates_ctl_vs_ctm():
    """Regression: et bredt CTL/CT-blacklistmønster må ALDRIG kunne overtrumfe
    et specifikt CTM-whitelistmatch, selvom begge dele deler 'CT'-præfikset."""
    assert classify_model("Festool CTL 26 til salg")["hard_reject"] is True
    assert classify_model("Festool CTM 26 sælges")["hard_reject"] is False
    assert classify_model("Festool CTM 26 sælges")["dust_class"] == "M"


def test_weak_evidence_alone_is_not_proof_of_class():
    """Spec: 'HEPA/professionel/industristøvsuger' er IKKE bevis for
    støvklasse -- skal give dust_class=ukendt + weak_evidence_only=True,
    ALDRIG en falsk H/M-klassifikation."""
    text = "Professionel industristøvsuger med HEPA 14 filter, 99,995% effektivitet"
    result = classify_model(text)
    assert result["dust_class"] == "ukendt"
    signals = extract_soft_signals(text)
    assert signals["weak_evidence_only"] is True


def test_explicit_class_statement_without_model_is_weaker_source():
    result = classify_model("Sælger byggestøvsuger, støvklasse H, ukendt mærke")
    assert result["dust_class"] == "H"
    assert result["klasse_kilde"] == "annoncetekst"
    assert result["model_key"] is None


def test_accessory_and_rental_ads_excluded():
    assert is_accessory_or_rental("Kun filter til salg til Kärcher NT 35/1")
    assert is_accessory_or_rental("Sikkerhedsfilterposer til salg, 10 stk")
    assert is_accessory_or_rental("Byggestøvsuger søges, helst H-klasse")
    assert is_accessory_or_rental("Udlejning af H-klasse støvsuger, pr. dag")
    assert not is_accessory_or_rental("Kärcher NT 35/1 Tact Te H sælges komplet med slange")


def test_soft_signals_detect_filter_cleaning_and_flowsensor():
    text = "Nilfisk Attix 30-0H PC med Tact-filterrensning, FlowSensor og stikdåse"
    signals = extract_soft_signals(text)
    assert signals["filterrensning"] == "automatisk"
    assert signals["flowsensor"] is True
    assert signals["stikdaase"] is True


def test_battery_detected_even_without_model_match():
    result = classify_model("Sikkerhedsstøvsuger, batteri, 18V, ukendt mærke, H-klasse nævnt")
    assert result["battery"] is True


def test_household_vacuum_categories_are_hard_rejected():
    """Regression -- fundet 2026-09-19 da brugeren manuelt diskvalificerede 9
    reelle DBA-fund (alle husholdningsstøvsugere), primært fra det brede
    'sikkerhedsstøvsuger'-søgeord. Disse produktkategorier kan KATEGORISK
    aldrig være en H/M-klasse maskine, uanset mærke/pris."""
    cases = [
        "Håndstøvsuger",
        "Helt ny håndstøvsuger 12v..",
        "Håndstøvsuger, AEG ukendt, 600 watt",
        "Aske Støvsuger",
        "Askepot til støvsugeren",
        "Kärcher askepot til støvsugeren",  # mærke nævnt -- skal STADIG hård-afvises
        "Lille støvsuger",
        "Robotstøvsuger Roomba sælges",
        "Bilstøvsuger 12V til salg",
        "Vinduesstøvsuger Kärcher WV2",
    ]
    for text in cases:
        result = classify_model(text)
        assert result["hard_reject"] is True, f"{text!r} skulle være hard_reject: {result}"


def test_generic_vacuum_bags_excluded_as_accessory():
    """Regression -- 'Kärcher støvsuger poser' blev IKKE fanget af det
    oprindelige mønster (kun 'filterposer'/'sikkerhedsfilterposer')."""
    assert is_accessory_or_rental("Kärcher støvsuger poser")
    assert is_accessory_or_rental("Poser til støvsuger, 10 stk")


def test_nilfisk_attix_without_class_letter_is_hard_rejected():
    """Regression -- Opus 5-gennemgang af live data (2026-09-20): 44% af al
    støj i en stikprøve på 25 ikke-afviste fund var Nilfisk Attix/Alto-
    modeller UDEN klassebogstav (Attix-seriens variant-tal ender på -0H/-2H
    for H, -2M for M, men -01/-11/-21/-51 er slet ingen klasse) -- disse
    slap tidligere igennem via known_brand_mentioned-fribilletten."""
    noise = [
        "Nilfisk Attix 50-21 XC",
        "Nilfisk Alto Attix 560-21 våd/tør støvsuger",
        "Nilfisk ATTIX 751-11 industristøvsuger blå",
        "Nilfisk Attix 751-51 vådstøvsuger industri",
        "Industristøvsuger NILFISK ATTIX 961-01",
        "Nilfisk Attix 9 961-01 industristøvsuger",
        "Industristøvsuger - Nilfisk Attix 965-21 DC XC",
        "Nilfisk Attix 961våd/tør støvsuger m. tilbehør",
        "Støvsuger NILFISK Attix 9 vandsuger",
        "Nilfisk Attix 33 støvsuger blå",  # har "33" (en H-model-familie), men INTET klassebogstav
    ]
    for text in noise:
        result = classify_model(text)
        assert result["hard_reject"] is True, f"{text!r} skulle være hard_reject: {result}"

    # Ægte H/M-whitelistede Attix-modeller (inkl. stavefejl-varianter, se
    # næste test) skal ALDRIG ramt af dette, da whitelisten tjekkes først.
    real = [
        "Nilfisk Attix 33-2H IC pæn",
        "Nilfisk Attix 30-0H PC",
        "Nilfisk Attix 50-0H PC",
        "Nilfisk Attix 965-0H SD XC",
        "Nilfisk Attix 751-0H Asbest",
        "Nilfisk Attix 44-2H IC",
        "Nilfisk Attix 33-2M PC",
        "Nilfisk Attix 995-0M SD XC",
        "Nilfisk Attix 550-0H",
    ]
    for text in real:
        result = classify_model(text)
        assert result["hard_reject"] is False, f"{text!r} blev fejlagtigt afvist: {result}"
        assert result["dust_class"] in ("H", "M"), f"{text!r}: {result}"


def test_nilfisk_attix_typo_variants_still_match_whitelist():
    """Regression -- rigtige stavefejl set i live data: 'Atto' (i stedet for
    Attix) og 'attik' (i stedet for Attix)."""
    assert classify_model("Nilfisk Atto 33 2H PC")["model_key"] == "nilfisk_attix_33_2h"
    assert classify_model("Nilfisk Alto attik 9 våd- og tørstøvsuger")["hard_reject"] is True


def test_karcher_nt_without_class_letter_is_hard_rejected():
    """Regression -- det oprindelige mønster dækkede kun 'NT 35/1'/'NT 30/1',
    men missede fx 'NT 45/1' og 'NT 30/1 Wet & Dry' (ingen 'Tact' i teksten)."""
    noise = [
        "Kärcher NT 45/1 Tact Te våd- og tørstøvsuger",
        "Kärcher NT 30/1 Wet & Dry Støvsuger 30 Liter",
        "Kärcher NT 65/2 Ap",
    ]
    for text in noise:
        result = classify_model(text)
        assert result["hard_reject"] is True, f"{text!r} skulle være hard_reject: {result}"

    real = [
        "Kärcher NT 35/1 Tact Te H",
        "Kärcher NT 30/1 Ap Te H",
        "Kärcher NT 75/1 Tact Me H",
        "Kärcher NT 50/1 Tact Te H",
    ]
    for text in real:
        assert classify_model(text)["hard_reject"] is False, text


def test_nilfisk_maxxi_and_bare_attix_number_hard_rejected():
    assert classify_model("Støvsuger, Nilfisk Atrixx maxxi wd 7")["hard_reject"] is True
    assert classify_model("Nilfisk Alto attik 9 våd- og tørstøvsuger")["hard_reject"] is True


def test_ronda_h_series_matched_generically():
    """Regression -- kun 'Ronda 2800 H' var whitelistet, men live-data viste
    'RONDA 80H 25L' og 'RONDA 1800H Power' som ægte H-klasse-fund."""
    for text, expected_key in [
        ("RONDA 80H 25L", "ronda_h_serie"),
        ("RONDA 1800H Power med opsamlingsspand", "ronda_h_serie"),
        ("Ronda 2800 H sælges", "ronda_2800h"),  # den specifikke, prissatte entry vinder
    ]:
        result = classify_model(text)
        assert result["model_key"] == expected_key, f"{text!r}: {result}"
        assert result["dust_class"] == "H"
    # Bevidst IKKE ramt -- rent tal uden H-suffiks er ikke en klasse-omtale.
    assert classify_model("Ronda 200 støvsuger")["model_key"] is None


def test_accessory_title_pattern_excludes_pose_boerste_slangesaet_ads():
    """Regression -- Opus 5-gennemgang: 'Nilfisk poser', 'Nilfisk børste',
    'Filterpose til Attix 751/761/961' og 'ATTIX 7 Liquid slangesæt' slap
    igennem det oprindelige tekst-tilbehørsfilter (som kun rammer titel+
    beskrivelse SAMLET, og bevidst er snævert for ikke at ramme en hel
    maskine der nævner medfølgende poser i beskrivelsen)."""
    accessory_titles = [
        "Nilfisk poser",
        "Nilfisk børste , Nilfisk",
        "Nilfisk Filterpose til Attix 751/761/961",
        "Nilfisk Alto ATTIX 7 Liquid slangesæt",
        # R11 (Opus 5-gennemgang af live resultater, 2026-09-20): disse to
        # blev fejlagtigt godkendt som 'valideret' (rigtigt modelmatch i
        # titlen overtrumfede tilbehørs-signalet) -- se normalize.py's R11.
        "Sicherheitsfiltersack für Attix 30-0H PC, 5er Pack",
        "Bosch GAS 35 H AFC 8x PE-Säcke",
    ]
    for title in accessory_titles:
        assert is_accessory_title(title), title

    # En hel maskine der NÆVNER tilbehør i titlen må ikke rammes -- den
    # matcher en whitelistet model, så is_accessory_title() må returnere False.
    whole_machine_titles = [
        "Nilfisk Attix 33-2H PC med 5 nye filterposer og slange",
        "Kärcher NT 35/1 Tact Te H, ekstra poser",
        "RONDA 1800H Power med opsamlingsspand",
    ]
    for title in whole_machine_titles:
        assert not is_accessory_title(title), title


def test_known_brand_mentioned_requires_a_model_like_number():
    """Regression -- Opus 5-gennemgang: 'Bosch støvsuger'/'Nilfisk
    støvsuger'/'NUMATIC STØVSUGER HEPA' havde intet modelnummer at
    verificere og blev ALLIGEVEL beskyttet mod afvisning af et kendt mærke
    alene -- en fribillet uden reelt indhold."""
    no_model_number = [
        "Bosch støvsuger",
        "Nilfisk støvsuger",
        "NUMATIC STØVSUGER HEPA",
        "Kärcher støvsuger poser",
    ]
    for title in no_model_number:
        assert extract_soft_signals(title)["known_brand_mentioned"] is False, title

    # Modstykke: et kendt mærke MED et modelnummer whitelisten ikke dækker
    # endnu skal STADIG beskyttes.
    assert (
        extract_soft_signals("Nilfisk Attix 44-0H industristøvsuger")["known_brand_mentioned"]
        is True
    )


def test_class_letter_signal_needs_a_domain_anchor():
    """Ny 2026-09-29 (Opus-review af intake/validering). Brugerens eget
    forslag -- "søg efter H i modelnavnet" -- generaliseret ud over
    whitelisten. Ankerkravet er hele forskellen mellem 47 % og 97 % præcision
    målt på 808 rigtige annoncetitler; alle titler herunder er hentet ordret
    fra live-data (Turso) eller fra probe-søgninger samme dag."""
    real_candidates = [
        # Suffiks-grenen
        "RONDA 80H 25 Industristøvsuger",
        "Baier BSS 608H våd-/tørsuger 1200W",
        "Bosch Professional Elektro-Nass- & Trockensauger GAS 35 H AFC",
        "RONDA 2800H Green Tech",
        # Fritstående-grenen -- ingen af disse har et tal foran bogstavet
        "Starmix H tør og våd støvsuger",
        "Asbest Sauger Sicherheitssauger H",
        "Starmix Vaccufix H støvsuger",
        "Nilfisk ATTIX 9 Industriesauger EX-Sauger Staubklasse H",
    ]
    for title in real_candidates:
        assert has_class_letter_signal(title), title

    # HELE støjbilledet fra det RÅ mønster uden anker (14 reelle af 30 fund).
    # Bemærk at H i fire af dem er et DÆKS HASTIGHEDSINDEKS, i én er timer,
    # i én en tysk veteranplade og i én et forstærker-HOVED.
    not_vacuums = [
        "4winterreifen+Alufelgen mercedes Bklasse 205/55R16 91H Brigestone",
        "✓ MERCEDES C-KLASSE W205 205/60 R16 92H WINTERRÄDER WINTERREIFEN",
        "4x Orig Mercedes-Benz Winterräder AMG 265/60 R18 110H G-Klasse A4",
        "Winterreifen 205/55 R16 91H mit Alufelgen für Mercedes C- Klasse",
        "⚡️Motorradanhænger mieten 24H➡️35€⚡️ Klasse B möglich",
        "Mercedes-Benz 380 SEC 126 H-Kennzeichen",
        "Topforstærker, Blackheart BH 100 H, 100 W",
    ]
    for title in not_vacuums:
        assert not has_class_letter_signal(title), title


def test_class_letter_signal_is_exposed_as_a_soft_signal():
    signals = extract_soft_signals("Starmix H tør og våd støvsuger")
    assert signals["klassebogstav_signal"] is True
    # ... men det er IKKE bevis for klassen: klasse_kilde sættes ikke herfra.
    assert classify_model("Starmix H tør og våd støvsuger")["dust_class"] == "ukendt"


def test_safety_vacuum_vocabulary_is_its_own_signal():
    """De tre live-rækker der motiverede mønsteret: vi SØGTE efter dem
    ('Asbestsauger' er et af vores syv primære søgeord), fandt dem, og afviste
    dem så selv som 'intet identificerbart signal'."""
    for title in (
        "Asbestsauger",
        "Bosch Asbest-Sauger Industriestaubsauger",
        "Asbest Sauger Sicherheitssauger H",
        "NILFISK VHS010 EX Sicherheitssauger H Klasse",
    ):
        assert extract_soft_signals(title)["sikkerhedssuger_vokabular"] is True, title

    # Det bare ord "asbest" må ALDRIG alene tælle -- det dækker også det stik
    # modsatte (maskinen HAR kørt asbest), se ASBESTOS_SKU_MARKING_PATTERN.
    assert extract_soft_signals("Støvsuger, har kørt asbest")["sikkerhedssuger_vokabular"] is False


def test_industrial_category_pattern_is_multilingual_and_plural_tolerant():
    """Otte rigtige tyske/svenske annoncer havde INTET signal overhovedet,
    alene fordi husets mønstre kun dækkede dansk -- og brugerens eget
    Klaravik-eksempel faldt på den danske FLERTALSFORM."""
    for title in (
        "Industristøvsugere Electrostar Starmix IS 2 styk",  # brugerens eksempel
        "Nilfisk industridammsugare med slang",
        "Werkstattsauger Starmix ISP iPulse ARH-1635 Staubklasse H",
        "Bosch Asbest-Sauger Industriestaubsauger",
        "Kärcher Profi Nass-Trockensauger NT35/1EcoTE mit Gerätesteckdose",
        "Kärcher våd-/tørstøvsuger industristøvsuger",
    ):
        assert extract_soft_signals(title)["industri_kategori"] is True, title

    # Det bare kategori-ord er BEVIDST ikke med: målt 38 fund, ~3 relevante.
    for title in ("Bosch dammsugare rosa med teleskoprör", "Nilfisk Compact dammsugare röd"):
        assert extract_soft_signals(title)["industri_kategori"] is False, title


def test_model_token_survives_a_dust_class_m_suffix():
    """Regression: '_SPEC_UNIT_PATTERN' læste det fritstående M i 'VC 60 M-X'
    som enheden METER og strippede modelnummeret. Konsekvensen var at en ægte
    M-klasse-maskine til 6.230 kr. på blocket.se blev afvist som 'intet
    identificerbart signal'."""
    assert has_model_token("Hilti VC 60 M-X")
    assert extract_soft_signals("Hilti VC 60 M-X")["known_brand_mentioned"] is True
    # Ægte enheder skal stadig strippes.
    assert not has_model_token("Støvsuger 1500 watt")
    assert not has_model_token("Slange 10 mtr")


def test_german_compound_adapter_counts_as_accessory():
    """Det ENESTE falske positive fund klassebogstav-valideringen producerede
    på 808 rigtige titler -- '254 M' er savklingens diameter i mm."""
    assert is_accessory_title("Absaugadapter für Nilfisk attix 30 auf Kappsäge Metabo KGS 254 M")


def test_letter_first_class_statement_is_recognised_but_anchored():
    """Ny 2026-09-29 (Opus-review): ordstillingen "H-klasse" (bogstav FØRST)
    blev slet ikke matchet -- EXPLICIT_CLASS_PATTERN krævede ordet "klasse"
    FØR bogstavet. Målt på 808 rigtige titler fandt den nye gren 10 annoncer,
    og alle ti var ægte H/M-maskiner."""
    for title in (
        "RONDA 40 HEPA H-KLASSE",
        "NUMATIC Rygstøvsuger RHB150NX H-klasse",
        "Festool CTH 26 dammsugare (H-klass) + tillbehör",
        "Flex-industristøversuger VCE44-AC H-klasse",
        "Sicherheitssauger H Klasse, ukendt mærke",
    ):
        result = classify_model(title)
        assert result["dust_class"] == "H", title
        # STADIG kun annoncetekst -- svagere end et modelnavn, jf. spec.
        assert result["klasse_kilde"] == "annoncetekst", title

    assert classify_model("Starmix industristøvsuger – M-klasse")["dust_class"] == "M"

    # HARD_REJECT vinder stadig over et klasse-udsagn i teksten, og det er med
    # vilje: "Nilfisk Alto Attix 30-21 PC Staubsauger H Klasse" (set i
    # live-data) er en Attix-30-21, som ER en L-maskine -- sælgerens påstand
    # om H kan ikke omgøre modelnummeret. Jf. husets linje om hellere at
    # afvise for meget end at godkende for meget.
    assert classify_model("Nilfisk Alto Attix 30-21 PC Staubsauger H Klasse")["hard_reject"] is True

    # Ankeret: "<bogstav>-Klasse" er også den tyske BILserie-betegnelse. Uden
    # støvsuger-domænet må mønsteret ALDRIG udtale sig om en støvklasse.
    for title in (
        "Mercedes M-Klasse ML 320 sælges",
        "Mercedes C-Klasse W204 17 Zoll Alufelgen Reifen 225 45 r17 H",
    ):
        assert classify_model(title)["dust_class"] != "M", title
        assert classify_model(title)["klasse_kilde"] is None, title
