"""Regressionstest for models.py's priority_stars-felt og de nye modeller
tilføjet 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3A/3B/3C) samt
revisionen 2026-09-29 (stovsuger-modeloversigt2.md, version 3)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.models import MODEL_WHITELIST, priority_model_keys
from scraper.normalize import classify_model, extract_soft_signals


def test_priority_model_keys_groups_by_star_tier():
    keys_3 = set(priority_model_keys(min_stars=3))
    keys_2plus = set(priority_model_keys(min_stars=2))
    keys_1plus = set(priority_model_keys(min_stars=1))

    # 3A-modeller (★★★)
    assert "nilfisk_attix_33_2h" in keys_3
    assert "flex_vce44h_ac" in keys_3
    assert "bona_dcs25" in keys_3
    # 3B-modeller (★★) er IKKE i 3-stjerners-sættet, men er i 2+-sættet
    assert "nilfisk_aero_26_2h_pc" not in keys_3
    assert "nilfisk_aero_26_2h_pc" in keys_2plus
    # 3C-modeller (★) er kun i 1+-sættet
    assert "makita_vc3211h" not in keys_2plus
    assert "makita_vc3211h" in keys_1plus
    # Ikke-kuraterede modeller har priority_stars=0 og optræder ingen steder
    assert "protool_vcp260eh" not in keys_1plus


def test_every_model_key_referenced_by_priority_exists_in_whitelist():
    all_keys = {m.key for m in MODEL_WHITELIST}
    assert set(priority_model_keys(min_stars=1)) <= all_keys


def test_new_2026_09_28_models_matched_with_correct_dust_class_and_asbestos():
    cases = {
        "Bona DCS 25 industristøvsuger": ("bona_dcs25", "H", True),
        "Starmix ISC H-1225 Asbest": ("starmix_isc_h1225_asbest", "H", True),
        "Nilfisk IVB 965 SD XC industri": ("nilfisk_ivb965_sd_xc", "H", True),
        "Nilfisk AERO 21 H": ("nilfisk_aero_21h", "H", True),
        "Metabo ASR 35 H ACP": ("metabo_asr35h_acp", "H", False),
        "Makita VC3211H flot": ("makita_vc3211h", "H", None),
        "Starmix iPulse H-1635 Safe Plus": ("starmix_ipulse_h1635_safe_plus", "H", None),
        "Bygma ISC H-163 Safe": ("bygma_isc_h163_safe", "H", None),
        "Starmix Energetic SX-110080 H": ("starmix_energetic_sx110080h", "H", None),
    }
    for text, (expected_key, expected_class, expected_asbestos) in cases.items():
        result = classify_model(text)
        assert result["model_key"] == expected_key, text
        assert result["dust_class"] == expected_class, text
        assert result["asbestos_approved"] == expected_asbestos, text


def test_starmix_isc_h1625_distinct_from_battery_mpb_variant():
    """Regression: 'ISC H-1625' (corded, IKKE asbestvarianten ifølge
    stovsuger-modeloversigt.md) skal aldrig kollidere med 'ISC 1625 MPB H'
    (batteri-variant, whitelistet separat med battery=True)."""
    corded = classify_model("Starmix ISC H-1625 god stand")
    assert corded["model_key"] == "starmix_isc_h1625"
    assert corded["asbestos_approved"] is False

    battery = classify_model("Starmix ISC 1625 MPB H batteri")
    assert battery["model_key"] == "starmix_isc_1625_mpb_h"


def test_karcher_generic_nt_h_fallback_does_not_shadow_specific_entries():
    """Regression: den generiske NT+H-fallback (karcher_nt_h_serie) er
    placeret SIDST blandt H-entries og må aldrig overtrumfe et specifikt
    whitelistet NT-mønster (rækkefølge = disambiguering, se models.py)."""
    assert classify_model("Kärcher NT 35/1 Tact Te H")["model_key"] == "karcher_nt35_1_tact_te_h"
    assert classify_model("Kärcher NT 30/1 Ap Te H")["model_key"] == "karcher_nt30_1_ap_te_h"

    # Et NT-modelnummer der IKKE har sin egen entry, men har H efterstillet,
    # skal fanges af den generiske fallback i stedet for at forblive ukendt.
    generic = classify_model("Kärcher NT 45/1 Tact Te H pæn stand")
    assert generic["model_key"] == "karcher_nt_h_serie"
    assert generic["dust_class"] == "H"
    assert generic["asbestos_approved"] is None

    # Et NT-modelnummer uden nogen H/M-bogstav skal stadig IKKE matche
    # whitelisten (og rammes af HARD_REJECT_PATTERNS et andet sted).
    assert classify_model("Kärcher NT 45/1 Wet & Dry")["model_key"] is None


# ---------------------------------------------------------------------------
# stovsuger-modeloversigt2.md (version 3, 2026-09-29) -- se models.py's docstring
# ---------------------------------------------------------------------------


def test_attix_33_2h_is_no_longer_presumed_asbestos_approved():
    """KRITISK REGRESSION (stovsuger-modeloversigt2.md, afsnit 7A + rettelse
    8/9): et bart "Attix 33-2H"-match må ALDRIG give asbestos_approved=True.
    Sætningen "Dust class M and H certification including Asbestos", som
    version 1-2 brugte som stærkeste bevis, er serietekst og står ordret også
    på ATTIX 33-2M PC (varenr. 107412179), en M-maskine der ikke må køre
    asbest. Kun varenavnene er SKU-specifikke ("ASBES" på 107412183 / "BG BAU
    ASBEST" på 107419012), og de kan ikke udledes af IC/PC-suffikset -- både
    den mærkede 107419012 og den UMÆRKEDE 107412184 er "IC"."""
    for text in [
        "Nilfisk Attix 33-2H",
        "Nilfisk Attix 33-2H IC pæn stand",
        "Nilfisk Attix 33-2H PC sælges",
        "Nilfisk Atto 33 2H PC",  # stavefejl-variant, samme krav
    ]:
        result = classify_model(text)
        assert result["model_key"] == "nilfisk_attix_33_2h", text
        assert result["dust_class"] == "H", text
        assert result["asbestos_approved"] is None, (
            f"{text!r} må ikke præsumeres asbestgodkendt: {result}"
        )

    # Modstykke: brand-defaulten (_ASBESTOS_APPROVED_H_BRANDS) gælder STADIG
    # for de øvrige Nilfisk-Attix-H-modeller -- rettelsen er bevidst afgrænset
    # til 33-2H-familien, som er den eneste version 3 eksplicit trækker
    # tilbage (se "ÅBENT SPØRGSMÅL" i models.py's docstring).
    assert classify_model("Nilfisk Attix 30-0H PC")["asbestos_approved"] is True


def test_sku_specific_asbestos_marking_is_detected_as_soft_signal():
    """Det der ERSTATTER den tilbagetrukne modelpåstand: en SKU-specifik
    mærkning i selve annonceteksten. Se normalize.ASBESTOS_SKU_MARKING_PATTERN."""
    positives = [
        "Nilfisk Attix 33-2H PC ASBES sælges",  # varenavnets afkortede stavemåde
        "Attix 33-2H IC BG BAU ASBEST, komplet",
        "Nilfisk Attix 33-2H, varenr. 107412183",
        "Nilfisk Attix 33-2H IC 107419012",
    ]
    for text in positives:
        assert extract_soft_signals(text)["asbest_sku_maerkning"] is True, text

    # BEVIDST IKKE en SKU-mærkning: ordet "asbest" alene er tvetydigt -- det
    # dækker både sælgerens (muligvis afskrevne) marketingpåstand OG det stik
    # modsatte, at maskinen HAR kørt asbest. Ville ellers kunne hæve tilliden
    # til præcis den maskine man skal holde sig længst fra.
    negatives = [
        "Nilfisk Attix 33-2H, asbestgodkendt ifølge sælger",
        "Attix 33-2H, har kørt asbest",
        "Asbestsuger H-klasse sælges",
        "Nilfisk Attix 33-2H IC, varenr. 107412184",  # den UMÆRKEDE IC-SKU
    ]
    for text in negatives:
        assert extract_soft_signals(text)["asbest_sku_maerkning"] is False, text


def test_baier_bss608h_added_but_not_presumed_asbestos_approved():
    """Baier BSS 608H står i afsnit 7A's tabel, hvis overskrift lover
    "dokumenteret asbestegnethed OG sikkerhedspose" -- men modellens EGEN
    række har "Sikkerhedspose: ikke fundet", og dokumentet citerer intet
    model-specifikt asbestbevis for den. Tabelplacering != evidens."""
    result = classify_model("Baier BSS 608H H-klasse støvsuger 30 l")
    assert result["model_key"] == "baier_bss608h"
    assert result["dust_class"] == "H"
    assert result["asbestos_approved"] is None
    assert result["container_l"] == 30

    # Søstermodellerne fra afsnit 11's modelkode-dekodning (606L/607M/608H):
    # M klassificeres korrekt, L hård-afvises -- uden dem ville de få
    # known_brand_mentioned-fribilletten, nu hvor "Baier" er i KNOWN_BRANDS.
    assert classify_model("Baier BSS 607M")["dust_class"] == "M"
    assert classify_model("Baier BSS 606L")["hard_reject"] is True


def test_container_volumes_corrected_from_version_3():
    """Afsnit 7A/7C retter to volumener; begge landede i det tomme 36-39 l-hul
    mellem specens to prisloft-intervaller (se classify._price_category)."""
    assert classify_model("Nilfisk Attix 44-2H IC")["container_l"] == 37
    assert classify_model("Hilti VC 40H-X")["container_l"] == 36
    # Bekræftelser (allerede korrekte -- testet så de ikke regredierer)
    assert classify_model("Nilfisk AERO 26-2H PC")["container_l"] == 25
    assert classify_model("Bona DCS 25")["container_l"] == 16
    assert classify_model("Makita VC3211H")["container_l"] == 32
    # RONDA: rettelse 17 siger 14 l pose / 16 l beholder for 200H Power, men
    # det generiske Ronda-mønster dækker 80H/200H/1800H med hver sin
    # størrelse, så container_l forbliver BEVIDST None.
    assert classify_model("RONDA 200H Power")["container_l"] is None


def test_aero_26_2h_new_price_uses_documented_ean_spread():
    """Afsnit 12: prisspredningen på SAMME EAN er 2.569-4.269 kr. ("Tjek EAN,
    ikke navn"). Det er bredere og bedre belagt end afsnit 7B's enkeltstal, og
    strammer samtidig 70%-porten i classify.py."""
    result = classify_model("Nilfisk AERO 26-2H PC")
    assert result["price_new_dkk_low"] == 2569
    assert result["price_new_dkk_high"] == 4269


def test_attix_33_2h_new_price_corrected_to_documented_figures():
    result = classify_model("Nilfisk Attix 33-2H IC")
    assert result["price_new_dkk_low"] == 4999  # IC, afsnit 7A
    assert result["price_new_dkk_high"] == 5150  # PC, afsnit 7A


def test_m_class_ic_variants_are_classified_not_left_unknown():
    """Afsnit 6 anbefaler "Nilfisk Attix 33-2M IC" som førstevalg hvis
    asbestprøverne er negative, og afsnit 10 opregner 30-2M/33-2M/44-2M/50-2M.
    Mønstrene krævede tidligere et efterfølgende "PC", så IC-varianterne slap
    igennem som dust_class="ukendt"."""
    for text, expected_key in [
        ("Nilfisk Attix 33-2M IC", "nilfisk_attix_33_2m"),
        ("Nilfisk Attix 33-2M PC", "nilfisk_attix_33_2m"),
        ("Nilfisk Attix 30-2M IC", "nilfisk_attix_30_2m"),
        ("Nilfisk Attix 44-2M IC", "nilfisk_attix_44_2m"),
        ("Nilfisk Attix 50-2M PC", "nilfisk_attix_50_2m"),
        ("Flex VCE 44 M AC", "flex_vce44m_ac"),
        ("Makita VC3211M udgået model", "makita_vc3211m"),
    ]:
        result = classify_model(text)
        assert result["model_key"] == expected_key, text
        assert result["dust_class"] == "M", text
        assert result["hard_reject"] is False, text

    # H-søstermodellerne må ikke forstyrres af de bredere M-mønstre.
    assert classify_model("Makita VC3211H")["dust_class"] == "H"
    assert classify_model("Flex VCE 44 H AC")["dust_class"] == "H"
    assert classify_model("Nilfisk Attix 44-2H IC")["dust_class"] == "H"
    # ... og L-varianten skal fortsat hård-afvises.
    assert classify_model("Makita VC3211L")["hard_reject"] is True


def test_ronda_200_without_h_is_hard_rejected():
    """Afsnit 10 ("Ingen støvklasse": RONDA 2000, RONDA 200 uden H) +
    rettelse 22: "RONDA 200 uden H findes, men er født uden H-filtertrinnet"."""
    for text in ["Ronda 200 støvsuger", "RONDA 2000 industristøvsuger"]:
        assert classify_model(text)["hard_reject"] is True, text
    # H-varianterne er beskyttet af at whitelisten altid tjekkes først.
    for text in ["RONDA 200H Power", "RONDA 200 H Power", "Ronda 2800 H"]:
        result = classify_model(text)
        assert result["hard_reject"] is False, text
        assert result["dust_class"] == "H", text
