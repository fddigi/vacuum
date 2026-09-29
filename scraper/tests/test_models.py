"""Regressionstest for models.py's priority_stars-felt og de nye modeller
tilføjet 2026-09-28 (stovsuger-modeloversigt.md, afsnit 3A/3B/3C)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.models import MODEL_WHITELIST, priority_model_keys
from scraper.normalize import classify_model


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
