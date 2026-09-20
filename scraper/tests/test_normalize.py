"""Kritisk test af model-genkendelse mod specens egne 'kendte fælder'
(sektion 2.8) og blacklist -- disse SKAL fejle synligt hvis whitelist/
blacklist-rækkefølgen nogensinde ombyttes ved en fremtidig redigering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.normalize import (
    classify_model,
    extract_soft_signals,
    is_accessory_or_rental,
    is_accessory_title,
)


def test_whitelist_h_models_matched_correctly():
    cases = {
        "Kärcher NT 35/1 Tact Te H - god stand": ("karcher_nt35_1_tact_te_h", "H", True),
        "Nilfisk Attix 33-2H IC pæn": ("nilfisk_attix_33_2h", "H", True),
        "Festool CTH 26 EI byggestøvsuger": ("festool_cth26ei", "H", True),
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
