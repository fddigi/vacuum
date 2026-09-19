"""Kritisk test af model-genkendelse mod specens egne 'kendte fælder'
(sektion 2.8) og blacklist -- disse SKAL fejle synligt hvis whitelist/
blacklist-rækkefølgen nogensinde ombyttes ved en fremtidig redigering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.normalize import classify_model, extract_soft_signals, is_accessory_or_rental


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
