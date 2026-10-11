"""Regressionstest for bygbrugt.py's WAF-proof-of-work-løser og tabel-parser
-- se modulets docstring for den reverse-engineerede sc-verify-protokol
(hentet og læst direkte fra sitets eget klient-script, 2026-10-10)."""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.sources.bygbrugt import (
    _CATEGORY_SLUGS,
    _danish_decimal_to_float,
    _leading_zero_bits,
    _parse_rows,
    _solve_challenge,
)

# Verbatim fra tre rigtige kategori-sider, 2026-10-10 -- de tre forskellige
# kolonne-layouts sitet bruger (vindue: Type før Bredde; dør: intet Type-
# felt; brandglas: fire ekstra felter inkl. en strukturel "BD"-kolonne).
_WINDOW_ROW_HTML = (
    '<tr class="product-entry" data-id="203" data-contact="R">'
    '<td class="preview-image" data-preview="x.jpg"><img src="x.jpg" /></td>'
    '<td><a href="/vinduer/facadevinduer/faste-karme/rf09">RF09</a></td>'
    "<td>1</td><td>Fastkarm</td><td>130</td><td>256</td><td>Træ</td><td>Hvid</td><td>2</td>"
    '<td style="text-align:right;" data-order="1900">'
    '<a href="/vinduer/facadevinduer/faste-karme/rf09">1.900</a></td>'
    '<td style="display: none">'
    '<a href="/vinduer/facadevinduer/faste-karme/rf09">20 34 59 50</a></td>'
    '<td style="text-align:right; font-weight: bold;">'
    '<a href="/vinduer/facadevinduer/faste-karme/rf09">Mere</a></td><td></td></tr>'
)

_DOOR_ROW_HTML = (
    '<tr class="product-entry" data-id="242" data-contact="R">'
    '<td class="preview-image" data-preview="x.jpg"><img src="x.jpg" /></td>'
    '<td><a href="/doere/branddoere/bd30/rb14">RB14</a></td>'
    '<td class="clearfix"><div style="float:left; width:40%; text-align: center;">1</div>'
    '<div style="float:left; width:10%"></div>'
    '<div style="float:right; width:40%; text-align: center;"></div></td>'
    "<td>89</td><td>208</td><td>40</td><td>12,5</td><td>Blå</td><td>Nej</td><td>0</td>"
    '<td style="text-align:right;" data-order="1500">'
    '<a href="/doere/branddoere/bd30/rb14">1.500</a></td>'
    '<td style="display: none"><a href="/doere/branddoere/bd30/rb14">20 34 59 50</a></td>'
    '<td style="text-align:right; font-weight: bold;">'
    '<a href="/doere/branddoere/bd30/rb14">Mere</a></td><td></td></tr>'
)

_BRANDGLAS_ROW_HTML = (
    '<tr class="product-entry" data-id="2813" data-contact="F">'
    '<td class="preview-image" data-preview="x.jpg"><img src="x.jpg" /></td>'
    '<td><a href="/glas-og-glasdoere/brandglas/f524">F524</a></td>'
    "<td>4</td><td>E30</td><td>89</td><td>171</td><td></td><td></td><td>E30</td>"
    '<td style="text-align:right;" data-order="1500">'
    '<a href="/glas-og-glasdoere/brandglas/f524">1.500</a></td>'
    '<td style="display: none"><a href="/glas-og-glasdoere/brandglas/f524">20 34 59 50</a></td>'
    '<td style="text-align:right; font-weight: bold;">'
    '<a href="/glas-og-glasdoere/brandglas/f524">Mere</a></td><td></td></tr>'
)


def test_leading_zero_bits_matches_known_examples():
    """REGRESSION: en tidligere version af _leading_zero_bits() manglede at
    AKKUMULERE 4 bits pr. ledende nul-cifre (brugte kun `continue` uden at
    lægge til) -- den kunne derfor aldrig returnere mere end 3, og
    _solve_challenge() ville reelt aldrig terminere med D=16. Disse
    forventede værdier er udregnet i hånden fra selve hex->binær-definitionen,
    ikke fra koden selv."""
    assert _leading_zero_bits("0000abcd") == 16  # fire nul-cifre = 16 bits præcis
    assert _leading_zero_bits("00001bcd") == 19  # 4*4 + 3 (cifret "1" = 0001)
    assert _leading_zero_bits("1234abcd") == 3  # "1" (0001) -- 3 ledende nul-bits
    assert _leading_zero_bits("8000abcd") == 0  # "8" (1000) -- 0 ledende nul-bits
    assert _leading_zero_bits("4000abcd") == 1  # "4" (0100) -- 1 ledende nul-bit
    assert _leading_zero_bits("2000abcd") == 2  # "2" (0010) -- 2 ledende nul-bit
    assert _leading_zero_bits("1000abcd") == 3  # "1" (0001) -- 3 ledende nul-bit


def test_solve_challenge_produces_a_valid_nonce():
    """Bruger et fast, kunstigt token/difficulty (ikke et rigtigt live-
    challenge) for at holde testen deterministisk og hurtig -- selve
    algoritmen er den samme som mod det ægte site, kun input er syntetisk."""
    token = "deadbeef"
    difficulty = 8  # lavt nok til at løses på millisekunder i en test
    nonce = _solve_challenge(token, difficulty)
    digest = hashlib.sha256(f"{token}:{nonce}".encode()).hexdigest()
    assert _leading_zero_bits(digest) >= difficulty


def test_danish_decimal_notation():
    assert _danish_decimal_to_float("1.500") == 1500.0
    assert _danish_decimal_to_float("12,5") == 12.5
    assert _danish_decimal_to_float("") is None
    assert _danish_decimal_to_float(None) is None


def test_parse_rows_window_layout_type_before_dimensions():
    rows = _parse_rows(_WINDOW_ROW_HTML)
    assert len(rows) == 1
    row = rows[0]
    assert row["varenr"] == "RF09"
    assert row["width_cm"] == 130.0
    assert row["height_cm"] == 256.0
    assert row["price"] == 1900.0
    assert "Fastkarm" in row["description_parts"]
    assert "20 34 59 50" not in " ".join(row["description_parts"])
    assert "Mere" not in row["description_parts"]


def test_parse_rows_door_layout_no_type_column():
    """REGRESSION: dørtabellen har INTET Type-felt før Bredde/Højde (anderledes
    end vinduestabellen) -- et positions-fast regex antog fejlagtigt samme
    kolonnerækkefølge og gav 0 rækker, indtil parseren blev lavet
    værdi-baseret i stedet."""
    rows = _parse_rows(_DOOR_ROW_HTML)
    assert len(rows) == 1
    row = rows[0]
    assert row["varenr"] == "RB14"
    assert row["width_cm"] == 89.0
    assert row["height_cm"] == 208.0
    assert row["price"] == 1500.0


def test_parse_rows_brandglas_layout_with_extra_bd_column():
    rows = _parse_rows(_BRANDGLAS_ROW_HTML)
    assert len(rows) == 1
    row = rows[0]
    assert row["varenr"] == "F524"
    assert row["width_cm"] == 89.0
    assert row["height_cm"] == 171.0


def test_parse_rows_handles_multiple_rows_and_empty_html():
    rows = _parse_rows(_WINDOW_ROW_HTML + _DOOR_ROW_HTML)
    assert len(rows) == 2
    assert _parse_rows("<html><body>ingen produkter</body></html>") == []


def test_category_slugs_map_to_valid_subtype_hints():
    valid_hints = {"vindue", "terrassedoer", "branddoer", "doer_andet"}
    assert set(_CATEGORY_SLUGS.values()) <= valid_hints
    assert _CATEGORY_SLUGS["doere/branddoere/bd30"] == "branddoer"
    assert _CATEGORY_SLUGS["doere/terrasse-doere"] == "terrassedoer"
    assert _CATEGORY_SLUGS["glas-og-glasdoere/brandglas"] == "vindue"
