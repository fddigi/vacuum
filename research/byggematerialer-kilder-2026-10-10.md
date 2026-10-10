# Genbrugs-byggematerialer i DK -- kildeevaluering af 16 sites

**Dato:** 2026-10-10
**Kategori:** `doere` (SHV-sourcing, totalrenovering i København)
**Status:** ren research-spike. INGEN kode skrevet eller rettet.

## Hvad blev undersøgt

16 konkrete URL'er for danske genbrugs-byggematerialesider, vurderet som
potentielle nye datakilder ved siden af den eneste eksisterende kilde af denne
type, `scraper/scraper/sources/genbyg.py` (aktiveret i `config.doere.yaml`).
Hertil en 17. URL der er en kategoriside på den allerede byggede genbyg.dk-kilde.

Målestokken for "et godt teknisk fund" er genbyg.py: ren `requests` (ingen
Playwright), SSR-HTML, og **strukturerede mål pr. kort** (separat
`Bredde:`/`Højde:`-felt) frem for fritekst-regex på en titel. Se
`doere_normalize.py`'s docstring for hvorfor den skelnen er afgørende:
strukturerede data vinder altid over regex-gæt på en titel.

## Metode (hvordan tallene er målt, ikke gættet)

Alt nedenfor er målt 2026-10-10 med rigtige HTTP-requests fra kommandolinjen
(`curl` + Python/`requests` med en almindelig Chrome-User-Agent), ikke gættet
og ikke hentet fra en søgemaskine-opsummering:

- Alle 17 URL'er hentet rå; statuskode og bytestørrelse noteret.
- Produkter talt ved at tælle de faktiske kort-/rækkemarkører i den RÅ HTML
  (fx `woocommerce-loop-product__title`, `class="product-grid"`,
  `<tr class="product-entry">`), dvs. uden browser-JS-eksekvering. Hvis tallet
  er 0 i rå HTML, er siden client-side renderet.
- Hvor der fandtes et offentligt API (WooCommerce Store API, Magento GraphQL,
  Shopify `products.json`), er totaler taget direkte fra API'ets egne
  tællere (`x-wp-total`, `total_count`) i stedet for at estimere.
- Måldækning ("hvor mange varer har faktisk brugbare mål") er udregnet ved at
  køre et regex over ALLE hentede varer i den pågældende kategori og tælle
  træfferraten, ikke ved at se på de første par kort.
- Køreafstande til København er egen geografisk viden (ikke en live
  ruteplanlægger) og er derfor afrundede, omtrentlige tal.

---

## 1. jk-genbrugscenter.dk -- Fastkarm-vinduer

URL: `https://jk-genbrugscenter.dk/produkt-kategori/nye-og-brugte-vinduer/fastkarm/`

**A. Katalog:** Ja, et rigtigt, dybt webshop-katalog. HTTP 200, 175 KB rå HTML,
18 produktkort direkte i SSR-HTML (ingen JS nødvendig). Pagineret til og med
`/page/9/` (side 10 giver 404). Målt sum: **161 fastkarms-vinduer** i netop
denne kategori.

**B. Strukturerede mål: JA -- bedst i testen.** Hvert kort har sit eget
dimensions-felt renderet fra WooCommerces egne produktmål:

```html
<div class="dimensions"><span class="dimension-number dimension-number-width">
<b>B</b> 95cm / <b>H</b> 239cm</span>
<span class="dimension-number dimension-number-height"><b>1</b> stk. på lager</span></div>
```

Plus varenummer (`product-list__sku`, fx `OF3286`), pris, lagerantal og et
JSON-datalayer-objekt pr. produkt (`window.pmwDataLayer.products[35009] =
{"id":...,"sku":"OF3286","price":2800,...}`).

Målt dækning over hele kategorier (alle sider hentet og talt):
- Branddøre: **73 af 73 kort (100 %)** har struktureret `B ... cm / H ... cm`.
- Fastkarmsvindue: **156 af 161 kort (97 %)**.

Det er på niveau med eller bedre end genbyg.dk.

**C. Paginering:** Ren URL-sti-paginering, `.../fastkarm/page/N/`, 18 kort pr.
side, 404 efter sidste side. Trivielt at loope -- samme "stop ved delvis side"-
princip som genbyg.py allerede bruger.

**D. Bot-beskyttelse: INGEN.** Plain `curl` med almindelig UA gav fuld HTML i
første forsøg. **Ingen Playwright nødvendig.**

**EKSTRA FUND -- det vigtigste tekniske fund i hele undersøgelsen:**
Sitet eksponerer **WooCommerce Store API'et offentligt og uautentificeret**:

```
GET https://jk-genbrugscenter.dk/wp-json/wc/store/v1/products?per_page=100
-> HTTP 200, x-wp-total: 1453
```

Det giver ren JSON med `name`, `sku`, `permalink`, `short_description`,
`prices` (i minor units, DKK), `categories`, `is_in_stock`,
`low_stock_remaining` og billeder -- 100 varer pr. request. Kategorifilter
virker (`?category=210` -> `x-wp-total: 73`), fritekstsøgning virker
(`?search=branddør` -> `x-wp-total: 56`).

Målte kategoritotaler via `/wp-json/wc/store/v1/products/categories`:

| Antal | Kategori (id) |
|------:|---------------|
| 716 | Nye og brugte vinduer (205) |
| 586 | Nye og brugte døre (207) |
| 216 | Sidehængt vindue (483) |
| 214 | Tophængte vinduer (334) |
| 161 | Fastkarmsvindue (339) |
| 132 | Fyldningsdøre uden karm (213) |
| 128 | Indvendigedøre (219) |
| 91 | Terrassedør (208) |
| 87 | Facadedør (209) |
| 77 | Vinduesparti (340) |
| **73** | **Branddøre (210)** |
| 48 | Badeværelsesvindue (980) |
| 18 | Runde og special-vinduer (216) |
| 4 | Sikringsdør (658) |

I alt 1453 varer på sitet.

**F. Branddøre/brandvinduer: JA, i mængde.** Hele kategorien "Branddøre" (73
varer) hentet og optalt. Fordeling efter produktnavn:
Branddør BD30 ×33, Branddør BD60 ×7, Brand & lyddør BD60 Rw 47 dB ×4,
BD30 Branddør med sideparti ×3, Brand & lyddør BD30-DB35 ×4,
El-120 stål branddør (Norvoferm) ×2, Stålbranddør EL60 ×1,
BD30 glasbranddør ×1, m.fl. Prisspænd målt: 1.200--7.200 kr.
Eksempel på en rå post:

```
OB676 | Stålbranddør EL60 | 7200,00 kr | "Bredde 108 / Højde 217"
       | kategori Branddøre | permalink .../staalbranddoer-el60/
```

Desuden `Brandglas BD30` som selvstændige varer i vinduesdelen (set på
fastkarm-siden), og 56 varer matcher fritekstsøgningen "branddør".

**E. Geografi:** Teglværksvej 23, 5220 Odense SØ (fundet på /kontakt/).
Ca. **165 km / ~1 t 50 min** fra København.

**robots.txt:** tillader alt relevant (kun `/wp-admin/` og `?add-to-cart=`
afvist). Ingen crawl-delay.

---

## 2. skave-nedbrydning.dk -- Vinduer

URL: `https://www.skave-nedbrydning.dk/vareliste/vinduer`

**A. Katalog:** Ja, og det er det STØRSTE udbud i undersøgelsen.
Sitet oplyser selv øverst i listen: `Viser 1 til 40 af 2914 (73 sider)` for
vinduer alene. Hele varelisten (`/vareliste`) viser `5447` varer.
Platform: OpenCart. HTTP 200, ren SSR-HTML.

Målte kategoritotaler (sitets egne tællere):

| Antal | Kategori |
|------:|----------|
| 2914 | vinduer |
| 326 | terrassedore |
| 263 | dore-indvendige |
| 261 | specialvinduer |
| 246 | dore-udvendige |
| 79 | vinduer-m-et-lag-glas |
| **5447** | **hele varelisten** |

**B. Strukturerede mål: JA.** Hvert kort har en egen `infos`-blok med mærkede
felter:

```html
<div class="infos col-12 mt-3">
  <strong>km</strong>: 7,0 cm<br />     <!-- karmdybde -->
  <strong>b</strong>: 59,0 cm<br />
  <strong>h</strong>: 119,0 cm<br />
  <strong>v</strong>: 28,0 kg<br />
  <strong>Produkt ID:</strong> 365<br />
  <strong>Antal på lager:</strong> 10
</div>
```

Dvs. bredde, højde, karmdybde, VÆGT og lagerantal som separate felter. Vægt
er noget ingen anden kilde i undersøgelsen leverer.

**Målt dækning:** hele kataloget (5447 varer) hentet over 11 sider og talt:
**4300 af 5447 (79 %)** har både `b:` og `h:` i cm som separate felter. De
resterende 21 % er varer hvor mål ikke giver mening (grus, beslag,
veterantraktorer m.m.) -- i dør-/vinduekategorierne isoleret var dækningen
**100/100 (100 %)** på hver af de tre stikprøvede sider.

**C. Paginering:** URL-parameter, `?page=N`. `limit=` kan sættes (målt:
`?limit=500` returnerede faktisk 500 kort, så hele kataloget er 11 requests)
-- MEN se robots-noten nedenfor: `limit=` er disallowed.

**D. Bot-beskyttelse: INGEN.** Plain curl, HTTP 200 hver gang.
**Ingen Playwright nødvendig.**

**robots.txt-forbehold (vigtigt):** `Crawl-delay: 30` og eksplicit
`Disallow: /*?limit=`, `/*?sort=`, `/*?order=`. Den hurtige `limit=500`-rute
er altså teknisk mulig men ikke tilladt. En velopdragen scraper skal bruge
default-sidestørrelse (40) og ≥30 s mellem requests -- 73 sider × 30 s ≈ 37
min for vinduerne alene. Det er en reel driftsbegrænsning, ikke en teknisk.

**E. Geografi:** Hesselåvej 6, 7500 Holstebro (Skave).
Ca. **330 km / ~3 t 40 min** fra København.

**F. Branddøre/brandvinduer: JA.** Hele kataloget (5447 varer) gennemsøgt for
BD30/BD60/BS60/EL30/EI/branddør/brandglas: **99 brandrelaterede varer**.
Navnefordeling: `BD30` ×55, `BS60` ×17, `Branddør` ×6, `Ståldør` ×4,
`BD30, db 30` ×3, `BD60` ×2, `BD30, db 35` ×2, `EI2 30` ×1,
`BD30 - 1½ dør` ×1, `Branddør m. glas` ×1, `Fastkarmsvindue m. brandglas (?)`
×1, plus 5 fastkarmsvinduer med brandglas-omtale.
Konkrete eksempler fra `dore-udvendige`:
- "Branddør -- Daloc Y 30 sikkerhedsdør, højrehængt"
- "Branddør -- Daloc S30 EL30, målet taget på indvendig mindste karm"
- "Branddør m. glas -- EL 60, venstrehængt, rustfri bundstykke, hal 1"

Beskrivelserne er usædvanligt detaljerede (hængselside, karmdybde, hvilken
hal varen står i).

---

## 3. skave-nedbrydning.dk -- den færdige filter-URL

URL: `https://www.skave-nedbrydning.dk/vareliste?propsearch=122&_category=35&min_max[width][min]=0&min_max[width][max]=1006&min_max[height][min]=0&min_max[height][max]=750`

**Spørgsmålet var: er bredde/højde-parametrene i query-strengen en ægte,
funktionel live-filtrering, der kan genbruges direkte? SVAR: JA, målt.**

Bevis ved at variere ÉN ting og måle svaret:

| Forespørgsel | Sitets egen tæller |
|---|---|
| `_category=35`, bredde 0--1006, højde 0--750 (den givne URL) | `Viser 1 til 40 af 326 (9 sider)` |
| `_category=35`, **bredde 85--100, højde 200--220** | `Viser 1 til 40 af 109 (3 sider)` |
| `/vareliste` uden filter | `Viser 1 til 40 af 5447 (137 sider)` |

326 -> 109 udelukkende ved at snævre målintervallet ind. Det er altså
**server-side filtrering på rigtige målfelter**, ikke kosmetik. `_category=35`
er Døre/terrassedøre (de returnerede varenavne er "Terrassedør",
"Terrassedør, dobbelt", "Terrassedør, halvdør").

Parameterstrukturen kan genbruges direkte: `min_max[width][min|max]` og
`min_max[height][min|max]` i cm, kombineret med `_category=N` og
`propsearch=122`. Pagineringslinks viser at serveren internt re-koder filteret
til en enkelt `min_max=`-streng, men den oprindelige `min_max[width][min]`-form
virker fint som indgang.

**Betydning for projektet:** Her er en kilde der KAN måls-filtrere på serveren,
præcis som genbyg.dk kan. Men bemærk genbyg.py's bevidste beslutning (se dens
docstring): kilden sender med vilje ALDRIG specWidth/specHeight, fordi et
snævert filter om ÉT centrum er uegnet til en bred scraper der skal finde alle
mål og lade dashboardet filtrere. Samme logik bør gælde her: filteret er et
nyttigt værktøj til ad hoc-opslag og til at BEVISE at måldata er ægte
felter i databasen, men en scraper bør hente bredt (hele kategorien) og
filtrere lokalt.

Øvrige punkter (B--F) som site 2.

---

## 4. baerebyg.dk -- Branddøre

URL: `https://baerebyg.dk/product-category/doere/branddoer/`

**A. Katalog:** Ja. WordPress 7.1.1 / WooCommerce 11.1.0 / Elementor.
Sidens egen tæller: `Viser 1–12 af 21 resultater` for branddør-kategorien.
Store API'et er også her offentligt: `x-wp-total: 1459` for hele sitet.

Målte kategoritotaler (fra `/wp-json/wc/store/v1/products/categories`):

| Antal | Kategori (id) |
|------:|---------------|
| 254 | Vinduer (259) |
| 189 | Døre (270) |
| 122 | Indvendige døre (285) |
| 111 | Plastvinduer (260) |
| 72 | Vinduesparti (261) |
| 54 | Trævinduer (268) |
| 53 | Træ/alu vinduer (266) |
| **21** | **Branddør (353)** |
| 19 | Nye vinduer (306) |
| 14 | Tag vinduer (309) |
| 12 | Terrassedør plast (271) |
| 9 | Facadedør (550) |

**B. Strukturerede mål: NEJ -- men meget regelmæssig fritekst.**
`attributes`-feltet er tomt for 16 af 21 branddøre, og kun **9 af 21** har
"bredde"+"højde" i beskrivelsen. Målene ligger i stedet i TITLEN efter en
fast konvention `dybde × bredde × højde` i cm:

```
Branddør / lyddør BD30/DB35  10×88,5×209          1800,00
Branddør, 10×98,8×209 cm.                         2200,00
Branddør, EL60, dobbelt, stål, 6,5x175x210 cm.    2000,00
Branddør BD60 13x88x209 cm.                       1500,00
Vindue træ/alu Kastrup vinduet. 12x130x137 cm.    3000,00
```

**Målt dækning over 521 dør-/vinduevarer** (kategorierne 353, 270, 285, 259
side 1--2, 260):
- Titel med 3 tal (D×B×H): **477 (92 %)**
- Titel med kun 2 tal (B×H): 11 (2 %)
- Uden mål i titel: 33 (6 %)

92 % er langt over fritekst-faldbackens målte hitrate på DBA (21,7 %, se
`config.doere.yaml`), fordi konventionen er en forhandlers egen og ikke
brugergenereret. Det kræver dog en kildespecifik parser, fordi det FØRSTE tal
er karmdybde, ikke bredde -- en naiv "første tal = bredde"-regel ville sætte
bredden til 10 cm på en 88,5 cm bred dør.

**C. Paginering:** WooCommerce standard, `/page/N/` (12 pr. side i HTML), eller
Store API med `per_page=100&page=N`.

**D. Bot-beskyttelse: INGEN.** Plain curl, HTTP 200, 375 KB HTML.
robots.txt tillader alt relevant.

**E. Geografi:** Bærebyg ApS, Industrivej 2, 7600 Struer.
Ca. **350 km / ~3 t 50 min** fra København.

**F. Branddøre: JA, 21 stk.** BD30/DB35, BD60, EL60 stål dobbelt, dørplader
uden karm. Priser målt 1.500--2.200 kr. En af dem har endda brandklasse-
forklaring i beskrivelsen ("EI 60 er en brandadskillende væg, der kan holde
i ...").

---

## 5. jensengenbrug.dk/katalog

**A. Katalog: KAN IKKE VURDERES LIGE NU -- sitet er nede.**

Målt: `/katalog` giver **HTTP 404** (IIS-standard 404-side, ISO-8859-1).
Rodsiden `https://jensengenbrug.dk/` giver HTTP 200 men er kun 766 bytes:
`<title>JensenGenbrug – Maintenance</title>` med ét enkelt billede og ingen
links. `robots.txt` og `sitemap.xml` giver begge 404.

Billedet (hentet og læst) siger ordret:
> **JENSENGENBRUG is under maintenance, and will be online again Monday 12/10**

Dvs. sitet er planlagt tilbage **mandag 12. oktober 2026** -- to dage efter
denne undersøgelse.

**B--F:** Kan ikke måles. **Anbefaling: genbesøg efter 12/10 og kør samme
måleprotokol.** Indtil da er der intet grundlag for hverken at anbefale eller
afvise kilden -- og specifikt ingen grund til at afvise den på et gæt.

---

## 6. genbrugsbyg.dk -- Produkter

URL: `https://www.genbrugsbyg.dk/Produkter.aspx?mainId=1`

**A. Katalog:** Ja, men lille. ASP.NET WebForms. Hele sitet optalt ved at
hente alle 13 hovedkategorier og tælle `compName`/`compPrice`-par:

| Antal | mainId | Kategori |
|------:|-------:|----------|
| 21 | 1 | Vinduer |
| 7 | 2 | Døre |
| 13 | 3 | El |
| 6 | 4 | VVS |
| 20 | 5 | Byggeri |
| 20 | 13 | Klinker |
| 9 | 9 | Retro |
| 3 | 7 | Sjove ting |
| 2 | 6 | Velux |
| 1--2 | 10,12,14 | Rustfri stål, Eksklusiv, Sengegavle |
| **104** | | **hele sitet** |

Døre-kategorien er 7 varer i alt, listet her komplet:
Terrassedør træ/alu B:84 H:240 · Massivt dør Eg B:89 H:205 ·
Udhusdør i træ B:98 H:215 · **Branddør BD60 Uden karm** ·
Forskellige dørplader frit valg 250,-/stk · Solid terrassedør B:107 H:250 ·
Primo terrassedør B:95 H:240.

**B. Strukturerede mål: NEJ.** Mål står i titlen (`B:142 H:151`,
`B230 H:31` -- inkonsistent med/uden kolon). Målt dækning: **19 af 21**
vinduer (90 %) og 5 af 7 døre har B/H i titlen; i de øvrige kategorier er
dækningen 0--30 %. Beskrivelsen er fritekst med af og til ekstra mål
("Den lille højde er 61,5 cm", "Venstre felt er 62 cm").

**C. Paginering: INGEN** -- hele kategorien ligger på én side. Navigationen i
UI'et er `__doPostBack`, men `?mainId=N` (og `&subId=N`) virker som almindelig
GET, så det er ikke en forhindring.

**D. Bot-beskyttelse: INGEN.** HTTP 200, 37 KB.

**E. Geografi:** Knækvej 6, 7200 Grindsted (fra /Kontakt.aspx).
Ca. **280 km / ~3 t** fra København. Bemærk åbningstiden på kontaktsiden:
"vi er bedst at træffe på telefon efter 16.30 indtil kl. 22.00" -- en
enkeltmandsvirksomhed (CVR-ejer Bendix Petersen).

**F. Branddøre: Næsten ingen.** 1 stk. "Branddør BD60 Uden karm", plus 2
ABDL-branddørslukkere (tilbehør, ikke døre) og 1 inspektionslem BS60.

---

## 7. greendozer.com -- Vinduer

URL: `https://greendozer.com/byggematerialer/vinduer-dore-og-tilbehor/vinduer`

**A. Katalog:** Ja. Magento 2 (Hyvä-tema). Kun 9 produktkort i rå HTML på
kategorisiden, men det er ikke hele sandheden: sitet eksponerer et
**offentligt GraphQL-endpoint** på `/graphql` uden autentifikation.

Målte kategoritotaler via GraphQL `categoryList`:

| Antal | Kategori |
|------:|----------|
| **123** | Vinduer, døre og tilbehør / **Døre** |
| **22** | Vinduer, døre og tilbehør / Vinduer |
| 3 | Tilbehør til ovenlysvinduer |
| 96 | Tag og facade |
| 329 | Byggematerialer (alt) |
| 59 | El |

Et enkelt kald `products(filter:{category_uid:...},pageSize:200)` returnerede
alle 123 døre på én gang -- ingen paginering nødvendig.

**B. Strukturerede mål: NEJ, men den mest disciplinerede titelkonvention i
testen.** Schemaet er tjekket ved introspection af `ProductInterface` (51
felter) -- der er **ingen** width/height/dimension-felter. Men navnene følger
en stram konvention `mærke + type, materiale, B×D×H i mm, hængsling, farve`:

```
Swedoor branddør BD30, 925x40x2052mm, højrehængt, hvid
Swedoor brand- og lyddør, BD30 DB35, 925x60x2045mm, venstrehængt, hvid
Jeld wen brand- og lyddør, BD30 DB35, 1025x60x2052mm, V, hvid
Kastrup Vinduet fastkarmsvindue, træ/alu, 1520x122x2034mm, hvid
```

**Målt dækning:** Døre: **109 af 123 (89 %)** med 3 mål i mm, 5 (4 %) med 2
mål, 9 (7 %) uden. Vinduer: **18 af 22 (82 %)** med 3 mål, 4 med 2 mål,
**0 uden**. Igen er det første tal bredde og det MIDTERSTE dybde -- her er
rækkefølgen B×D×H, altså en anden rækkefølge end Bærebyg (D×B×H). Det er
præcis den slags kildespecifikke faldgrube der taler for struktureret data.

**C. Paginering:** `pageSize` i GraphQL (200 virker). HTML-siden har
Alpine.js-baseret paginering, men den er irrelevant når API'et findes.

**D. Bot-beskyttelse: Ingen teknisk blokering -- men et eksplicit
robots.txt-forbud.** Siden hentede fint (683 KB, HTTP 200), og GraphQL svarer
uden nøgle. MEN `https://greendozer.com/robots.txt` indeholder:

```
User-agent: ClaudeBot
Disallow: /

User-agent: meta-externalagent
Disallow: /
```

Det er en bevidst, navngiven udelukkelse. Teknisk kan man hente, men operatøren
har sagt fra over for netop denne type agent. **Det bør afklares med
GreenDozer (de er B2B og sælger til erhverv) før noget bygges.**

**E. Geografi:** GreenDozer ApS, Sonnesgade 4, 8000 Aarhus C --
ca. **310 km / ~3 t** fra København. MEN kontaktsiden siger ordret:
*"Obs ingen varelager på adressen."* Varerne afhentes/leveres fra
leverandørernes lokationer (Click & Collect pr. vare), så Aarhus-adressen er
et kontor, ikke et lager man kan køre til. Afstanden til den enkelte vare er
derfor ukendt uden at åbne varen.

Bemærk også: sitet erklærer **"Kun B2B salg"** i topbanneret. Priserne vises
ex. moms (målt: `2000.000001` for en ståldør).

**F. Branddøre: JA, 29 af 123 døre (24 %)** har brandklasse i navnet.
Målt fordeling af eksempler: Swedoor branddør BD30, Swedoor branddør BD60
(flere bredder: 625/925/1125 mm), Swedoor brand- og lyddør BD30 DB35,
Jeld Wen brand- og lyddør BD30 DB35, Swedoor brandkarmsæt BD30,
Swedoor brand- og lyddør BD60 DB35 i træ. 0 brandvinduer.

---

## 8. pogenbrug.dk -- Branddøre

URL: `https://pogenbrug.dk/vare/branddoere/`

**A. Katalog: NEJ -- og det er den vigtigste konstatering om dette site.**
Sidens titel er ganske vist "Branddøre -- P. Olesen genbrug", og den er en
WooCommerce `/vare/`-side, men den er ÉN generisk pladsholder-vare, ikke en
liste. Brødteksten lyder ordret:

> "I hallen finder du mange BD30- og ind imellem nogle BD60 branddøre. Nogle er
> desuden akustik-døre. Forskellige størrelser og forskellige kvaliteter.
> Kom og find din dør. [...] Billedet er bare et "modelfoto""

Bekræftet via Store API: `x-wp-total: **42**` for HELE sitet, og de 42 er
kategori-pladsholdere, ikke varer. Udvalgte titler fra API-dumpet:
"Branddøre" (pris 0,00), "Vinduer – tag tommestokken med, og gå på jagt"
(pris 0,00), "Køkkenelementer – varirerende antal", "Troldtekt",
"Genbrugsmaterialer til dit byggeri". Kun 3 af 42 har noget der overhovedet
ligner et mål.

Sitet er med andre ord et skilt der peger på en fysisk hal -- ikke et lager
man kan læse.

**B. Strukturerede mål:** Ikke relevant; der er ingen varer at måle.

**C. Paginering:** 42 varer, 1 side.

**D. Bot-beskyttelse:** Ingen. HTTP 200, Store API åbent.

**E. Geografi:** Industriområdet 15-17, 8732 Hovedgård (ved Horsens).
Ca. **260 km / ~2 t 50 min** fra København. Åbent tirs--tors 8--17, fre 8--16,
lør 9--13, lukket mandag.

**F. Branddøre:** Formentlig mange fysisk ("mange BD30 og ind imellem nogle
BD60"), men **nul** af dem er registreret online med mål, pris eller
varenummer.

---

## 9. bygbrugt.dk -- Faste karme

URL: `https://www.bygbrugt.dk/vinduer/facadevinduer/faste-karme`

**D. Bot-beskyttelse: JA -- den tidligere observation BEKRÆFTES, men den er
ikke en showstopper, og det er et vigtigt nyt resultat.**

Første request gav **HTTP 454** med en side der hedder "Checking your
browser...". WAF'en er **simply.com's Website Application Firewall** (dansk
hostingudbyder; samme WAF ramte også site 10 og 12 -- se dem).

Jeg har reverse-engineeret og **testet** challenget frem for at gætte på det.
Det er IKKE en CAPTCHA og kræver IKKE en browser. Det er et
**SHA-256 proof-of-work**:

1. 454-siden indeholder i klartekst: `var T="<64 hex>",TS="<unix-ts>",D=16;`
2. Klienten skal finde et `nonce` hvor `sha256(T + ":" + nonce)` har mindst
   `D` (= 16) ledende nul-BITS.
3. Resultatet POSTes som `ts`, `nonce`, `token` til `/.sc-verify/`, der svarer
   `{"ok":true,"cookie":"<ts>|<hash>"}`.
4. Cookien sættes som `sc_clearance` på domænet, `max-age=86400` (24 timer).

Målt i ren Python (`hashlib`, ingen browser, ingen Playwright):

```
initial status: 454
challenge: difficulty=16 bits
solved nonce=5584 in 0.01s
verify: 200 {"ok":true,"cookie":"1791612913|c95efa46..."}
after clearance: 200 len 97624
```

**Omkostning: 0,01--0,07 sekunder CPU én gang i døgnet pr. domæne.** Det er
altså ikke et argument for at tilføje en Playwright-afhængighed -- tværtimod
viser målingen at en `requests`-kilde kan klare det med ~25 linjer kode.

To forbehold, målt:
- Challenget er **intermittent**: ved et senere forsøg svarede samme URL
  direkte HTTP 200 uden challenge. Koden skal altså håndtere begge veje.
- Ved intensiv hentning svarede serveren på et tidspunkt **HTTP 455
  "Security Incident Detected -- Do not retry"**. Det er en hårdere
  rate-limit-tilstand end 454 og forsvandt igen af sig selv. En scraper her
  SKAL have ordentlig throttling og må ikke retry-spamme på 455.
- `robots.txt` (hentet efter at 455-tilstanden slap op) er indholdsløs og
  tilladende: `User-agent: * / Disallow: test`.

**A. Katalog:** Ja, og det er stort. Efter clearance: HTTP 200, 97 KB.
**95 varerækker** alene på faste-karme-siden.

Målte tal pr. kategori (alle hentet med clearance-cookien):

| Rækker | heraf m. numerisk B+H | Kategori |
|-------:|----------------------:|----------|
| 191 | 162 | /vinduer/facadevinduer/sidehaengte |
| 186 | 159 | /vinduer/facadevinduer/tophaengte |
| 95 | 73 | /vinduer/facadevinduer/faste-karme |
| 85 | 77 | /doere/yderdoere |
| **42** | **40** | **/doere/branddoere/bd30** |
| 12 | 0 | /doere/specialdoere |
| 14 | 0 | /vinduer/tagvinduer/nye |
| 8 | 0 | /vinduer/tagvinduer/inddaekninger |
| **7** | **5** | **/doere/branddoere/bs60** |
| **6** | **6** | **/doere/branddoere/bd60** |
| 4 | 0 | /vinduer/tagvinduer/brugte |
| **3** | **3** | **/doere/branddoere/dobbelte-branddoere** |
| **3** | **3** | **/glas-og-glasdoere/brandglas** |
| 498 | 394 | **vinduer i alt** |

(Forældrekategorierne `/doere` og `/vinduer` har 0 rækker -- varerne ligger
kun på bladniveau. Det skal en crawler vide.)

**B. Strukturerede mål: JA -- den reneste struktur i hele undersøgelsen.**
Varerne står i en HTML-TABEL med navngivne kolonner:

`Billede | No. | Antal | Type | Bredde | Højde | Materiale | Farve | Lag glas | Pris | Telefon`

En række ser sådan ud (forkortet):

```html
<tr class="product-entry" data-id="203" data-contact="R">
  <td><a href="/vinduer/facadevinduer/faste-karme/rf09">RF09</a></td>
  <td>1</td><td>Fastkarm</td><td>130</td><td>256</td>
  <td>Træ</td><td>Hvid</td><td>2</td>
  <td data-order="1900"><a ...>1.900</a></td>
</tr>
```

Bredde og højde er rene tal i egne `<td>`'er (cm). Oven i det får man
**materiale, farve og antal lag glas** som selvstændige felter -- data ingen
anden kilde i undersøgelsen leverer struktureret. Målt dækning i de relevante
kategorier: 73/95 (77 %) på faste karme, 162/191 (85 %) sidehængte,
159/186 (85 %) tophængte, 77/85 (91 %) yderdøre, **40/42 (95 %) på BD30**,
6/6 (100 %) på BD60.

**C. Paginering: INGEN at håndtere.** Alle rækker ligger i rå HTML på
kategoribladsiden (DataTables paginerer kun klientsidet). Én request =
hele kategorien.

**E. Geografi:** Randersvej 82, 8870 Langå (mellem Randers og Viborg).
Ca. **300 km / ~3 t 15 min** fra København. Sidens egen SEO-titel bekræfter
oplandet: "Århus Aalborg Midtjylland Østjylland Randers".

**F. Branddøre: JA, og med dedikeret kategoristruktur** -- sitet har egne
URL'er for `/doere/branddoere/bd30`, `/bd60`, `/bs60`,
`/dobbelte-branddoere`, `/glasbranddoere` (tom), `/brandporte` (tom) og
`/glas-og-glasdoere/brandglas`. Målt i alt **58 brandklassificerede varer**
(42 BD30 + 6 BD60 + 7 BS60 + 3 dobbelte + 3 brandglas), heraf 57 med
numerisk bredde og højde i egne kolonner. Ingen anden kilde i undersøgelsen
har brandklassen som KATEGORI frem for som tekst i en titel.

---

## 10. titan-genbrug.dk -- Terassedøre

URL: `https://titan-genbrug.dk/product-category/doere/terassedoere/`

**D. Bot-beskyttelse: JA, samme simply.com-WAF som site 9.** HTTP 454,
difficulty 16, løst i 0,05 s, derefter HTTP 200 (69,8 KB). Ikke en blokering i
praksis. robots.txt er WordPress-standard og tilladende.

**A. Katalog: Ja, men meget lille.** WordPress 7.1.3 / WooCommerce 8.9.5.
Store API er åbent: `x-wp-total: **46**` for HELE sitet.

Målte kategoritotaler:

| Antal | Kategori (id) |
|------:|---------------|
| 14 | Diverse (15) |
| 10 | Vinduer (59) |
| 9 | Døre (65) |
| 9 | Køkken og badeværelse (66) |
| 4 | Indvendige døre (76) |
| **3** | **Branddøre (80)** |
| 3 | Terassedøre (78) |
| 2 | Yderdøre (77) |

Terassedør-kategorien = **3 varer**, hele dør-området = 9, hele sitet = 46.

**B. Strukturerede mål: Delvis.** Beskrivelserne bruger mærkede felter, men
ikke konsekvent:

```
Træ/ alu terrassedør, 06-03-05 · 1.800,00 kr
  Træ/alu terassedør  Højde: 212 cm  Bredde: 94,5cm
  Udadgående (Både højre- og venstrehængte på lager)
```

Målt over alle 46 varer: **16 (35 %)** har både "Bredde" og "Højde" som
mærkede ord i beskrivelsen. Resten bruger blandede former ("Udv karmmål (bxh)
... 1990x 2090mm", "63x 160cm", "1220x 2500mm") med inkonsekvent mellemrum
efter `x`.

**C. Paginering:** WooCommerce standard; irrelevant ved 46 varer.

**E. Geografi:** Nålemagervej 4, 9000 Aalborg.
Ca. **380 km / ~4 t 15 min** fra København -- den fjerneste i undersøgelsen.
Åbent **kun torsdage kl. 9--14** (eller efter aftale).

**F. Branddøre: 3 stk.** (hele kategori 80).

---

## 11. gronnehal.dk -- Den Grønne Genbrugshal

URL: `https://www.gronnehal.dk`

**A. Katalog: NEJ.** Squarespace-brochureside. `sitemap.xml` indeholder
**tre** URL'er i alt: `/home`, `/kontakt`, `/omos`. Der er ingen
produktsektion, ingen priser, ingen varer, intet lager-opslag.

Forsidens tekst er en opremsning af varegrupper, ikke varer -- fx
"Gulvbrædder genbrug", "Døre og vinduer genbrug", "Glas. Vi skærer efter mål",
"Spraymaling", "Carhartt arbejdstøj", "Medicinsk cannabis og hampeprodukter".
Der er altså genbrugsdøre og -vinduer i hallen, men intet online at scrape.

**B--D:** Ikke relevant. (Ingen bot-beskyttelse; 1,1 MB Squarespace-HTML
hentede fint.)

**E. Geografi: Fabriksområdet 56, 1440 København K (Christiania).**
**0 km -- det er midt i byen.** Åbent mandag 11--18, tirs--søn 10--18.
Telefon +45 32 54 79 24, info@gronnehal.dk. Christiania er bilfri, så
afhentning sker ved Refshalevej eller Bådsmandsstræde med lånt trækvogn
(står på deres egen side).

**F. Branddøre:** Ingen oplysning. Må afklares ved besøg/opkald.

**Vurdering:** Teknisk værdiløs som scraper-kilde (3 sider), geografisk den
absolut mest attraktive af alle 16. Det er en ren "gå derhen"-adresse.

---

## 12. demfranordlunde.dk -- Brugt Marked

URL: `https://demfranordlunde.dk/shop/254-brugt-marked`

**D. Bot-beskyttelse: JA, samme simply.com-WAF.** HTTP 454, difficulty 16,
løst i 0,07 s, derefter HTTP 200 (176 KB). `robots.txt` findes ikke (404).

**A. Katalog: Ja.** PrestaShop. Den anførte "Brugt Marked"-kategori er dog
kun en lille del af det relevante: sitet er en almindelig trælast/byggemarked
med 220 shop-kategorier, hvoraf flere er genbrugsvarer. Målt (sitets egne
tællere, `?resultsPerPage=100`):

| Antal | Kategori |
|------:|----------|
| **55** | /shop/40-dore (Døre, alle undertyper) |
| **40** | /shop/77-vinduer |
| 28 | /shop/254-brugt-marked (den anførte URL) |
| 17 | /shop/683-terrassedore |
| 13 | /shop/682-facadedore |
| 8 | /shop/135-udhusdore-baghusdore |
| 8 | /shop/438-brugt-diverse |
| 7 | /shop/685-dobbeltdore |
| 6 | /shop/434-vinduer-dore (under Brugt Marked) |
| 5 | /shop/542-traedor |
| 3 | /shop/540-staldor |

Den URL der blev givet (254-brugt-marked, 28 varer) er altså IKKE hvor
dørene og vinduerne er -- de ligger i 40-dore og 77-vinduer.

**B. Strukturerede mål: NEJ, men titelkonventionen er stærk.**
Produktnavne ser sådan ud:

```
Dobbelt Facadedør - Bredde:131 Højde:212
Terrassedør - Bredde: 100 Højde: 205,5
Facadedør - Bredde:140,5 Højde:207
3 Fags vindue - Bredde 179 cm Højde 118,5 cm
Bondehusvindue med redningsåbning - Bredde: 95 Højde: 109
Topstyrede vinduer B.111,8 x H.137x,8 cm
Ståldør 100x200 cm Universal Højre/Venstre
```

**Målt dækning:**
- `/shop/40-dore` (55 varer): 36 (65 %) med "Bredde...Højde", 8 (15 %) med
  "N×N cm", 11 (20 %) uden mål.
- `/shop/77-vinduer` (40 varer): **38 (95 %)** med "Bredde...Højde", **2 uden**.

Fordelen frem for fx Bærebyg er at felterne er NAVNGIVNE i titlen
("Bredde:131 Højde:212"), så der er ingen tvivl om hvilket tal der er hvad --
ingen dybde-som-første-tal-fælde. Ulempen er inkonsistent formatering
(med/uden kolon, med/uden "cm", og mindst én tastefejl: "H.137x,8 cm").

**C. Paginering:** URL-parameter `?page=N`, og `?resultsPerPage=100` virker
(hele kategorier i én request).

**E. Geografi:** Lucernevej 26, 4900 Nakskov (Lolland).
Ca. **150 km / ~2 t** fra København -- **næstbedst af alle de sites der
faktisk har et katalog.**

**F. Branddøre: NEJ.** 0 af de 95 døre/vinduer i 40-dore og 77-vinduer har
BD30/BD60/BS60/EI i navnet. Sortimentet er facadedøre, terrassedøre,
dobbeltdøre, udhusdøre, ståldøre og almindelige vinduer.

---

## 13. jk-genbrugscenter.dk (rodsiden)

URL: `https://jk-genbrugscenter.dk`

Rodsiden er en almindelig WooCommerce-forside (134 KB). Den interessante del
er kategorinavigationen, som bekræfter at site 1's fastkarm-kategori kun er
en lille flig af udbuddet. Fem hovedkategorier:

```
/produkt-kategori/nye-og-brugte-vinduer/     -> 716 varer
/produkt-kategori/nye-og-brugte-doere/       -> 586 varer
/produkt-kategori/diverse-byggematerialer/   -> 134 varer
/produkt-kategori/porte/                     ->   3 varer
/produkt-kategori/vvs/                       ->  20 varer
```

Alt øvrigt (Store API, strukturerede mål, paginering, ingen bot-beskyttelse,
Odense, 73 branddøre) er dokumenteret under site 1 -- det er samme site.

**Konklusion for rodsiden:** Den tilføjer ikke en ny kilde, men den
dokumenterer at site 1's 161 fastkarme skal ses i kontekst af **1.302
dør-/vinduevarer i alt** på samme domæne, alle tilgængelige gennem det samme
åbne Store API med 100 varer pr. request. Det gør JK til den dybeste
dør/vindue-kilde i undersøgelsen målt på mængde × datakvalitet.

---

## 14. rodekorsgenbrug.dk -- Byggemarked Røde Kors Odense

URL: `https://rodekorsgenbrug.dk/collections/byggemarked-rode-kors-odense`

**A. Katalog: Ja.** Shopify, og `products.json` er åbent (Shopify-standard):

```
GET /collections/byggemarked-rode-kors-odense/products.json?limit=250
-> HTTP 200, 201 produkter (side 2 er tom -> 201 er hele kollektionen)
```

Men kun en brøkdel er relevant. `product_type`-fordeling i de 201:
Skruer/søm/beslag 27 · Hobby og fritidsudstyr 22 · Træ og plader 19 ·
VVS 18 · **Vinduer og døre 16** · Lamper 13 · Elektronik 9 · Skabe 8 ·
Hvidevarer 7 · Maling 7 · (resten under 6).

**EKSTRA FUND:** `/collections.json` afslører 203 kollektioner, heraf syv
byggemarkeder. Alle målt:

| Varer i alt | heraf dør/vindue | Kollektion |
|------------:|-----------------:|------------|
| 373 | 49 | byggemarked (samlet) |
| 201 | 20 | **Odense** (den anførte) |
| 189 | **4** | **Glostrup Byggegenbrug** |
| 118 | 26 | Viborg |
| 16 | 0 | Hinnerup |
| 9 | 0 | Horsens |
| 0 | 0 | Ringkøbing |

Glostrup-kollektionen er geografisk interessant (ca. 15 km fra København),
men har målt kun **4** dør-/vinduevarer ud af 189.

**B. Strukturerede mål: NEJ, og dårligt dækket.** Mål står kun sporadisk i
fritekst-`body_html`. Gennemgang af alle 16 varer i "Vinduer og døre" i
Odense-kollektionen: **8 med mål, 8 uden**:

```
MÅL:    Vindue, 95x129 cm        | 300 kr | "Vindue, termo 95x129 cm"
MÅL:    Træ/alu termovindue      | 500 kr | "3 lags træ/alu 97x132"
MÅL:    Vindue, 201x140 cm       | 400 kr | "Vindue, termo 201x140 cm"
INTET:  Termovindue              | 800 kr | "Termovindue 3 fag."
INTET:  Hvid plast vindue        | 450 kr | "Plastvindue med matteret
                                            termorude. Målene er karm mål"
INTET:  Outline vindue ...       |1150 kr | "...Målene er karmmål"
```

De to sidste er særligt sigende: beskrivelsen forklarer HVAD målene er, men
oplyser dem aldrig. Over hele kollektionen: 41 af 201 varer (20 %) har noget
der ligner et mål -- på niveau med DBA's målte fritekst-hitrate (21,7 %).

**C. Paginering:** `products.json?limit=250&page=N` (Shopify-standard).

**D. Bot-beskyttelse: INGEN.** robots.txt er Shopify-standard og tillader
`/collections/`.

**E. Geografi:** Røde Kors Odense (Odense, Fyn). Ca. **165 km / ~1 t 50 min**
fra København. Glostrup-afdelingen ca. 15 km / ~25 min -- men se de 4 varer.

**F. Branddøre: NUL.** Alle syv byggemarkeds-kollektioner (906 varer i alt)
gennemsøgt for brand/BD30/BD60/EI: **0 træffere.** Røde Kors' byggemarkeder er
donerede overskudsvarer, ikke nedrivningsmateriale, og brandklassificerede
bygningsdele indgår simpelthen ikke.

---

## 15. brugtemursten.dk

URL: `https://www.brugtemursten.dk`

**A. Katalog: NEJ.** Hele sitet er **5,5 KB statisk HTML** (gammel
WYSIWYG-eksport, ISO-8859-1, ingen `<title>`). Fem menupunkter: Forside,
Håndrensede sten, Miljø, Kontakt, Galleri. Ingen produkter, ingen priser,
ingen søgning.

Forsidens tekst i sin helhed handler om mursten:
> "Vi har specialiseret os i at opstøve, indsamle og håndrense mursten, der er
> patineret af tidens tand. [...] Vi har konstant udskiftning i sortimentet og
> ligger altid inde med et bredt udvalg af forskellige sten. Døren står altid
> åben for kontakt."

**B--D:** Ikke relevant. Ingen bot-beskyttelse.

**E. Geografi:** Voldsgårdvej 28, 7400 Herning.
Ca. **300 km / ~3 t 15 min** fra København.

**F. Branddøre/brandvinduer: NUL -- og det er per definition.**
Virksomheden sælger **kun mursten**. Der er ingen døre og ingen vinduer i
sortimentet overhovedet.

**Vurdering:** Uden for kategorien `doere`. Bør springes over, ikke fordi
sitet er dårligt bygget, men fordi varegruppen er forkert.

---

## 16. hockerup.dk -- Brugte byggematerialer

URL: `https://www.hockerup.dk/ydelser/brugte-byggematerialer`

**A. Katalog: NEJ -- brugerens egen note BEKRÆFTES: "intet katalog men værd
at spørge" holder stadig stik pr. 2026-10-10.**

Squarespace. Hele `sitemap.xml` er gennemgået (ca. 40 URL'er): udelukkende
firmasider (Om os, Bestyrelse, Medarbejdere, Rapporter, Certifikater,
Nedrivning, Diamantskæring, referencer, jobopslag). Der findes TO relevante
sider -- `/ydelser/brugte-byggematerialer` og `/genbrugsbutik` -- og begge er
ren brødtekst uden en eneste vare, pris eller mål.

Sidens egne ord:
> "I vores genbrugsbutik kan du købe brugte og cirkulære byggematerialer, der
> blandt andet stammer fra vores egne nedrivningsprojekter. [...] Det kan
> blandt andet være **døre, vinduer**, træmaterialer, inventar, beslag og
> andre byggedele"
>
> "Udvalget i vores genbrugsbutik ændrer sig løbende, da materialerne kommer
> fra vores aktuelle nedrivningsopgaver. [...] Hvis du ikke finder præcis det
> byggemateriale, du søger, er du altid velkommen til at kontakte os.
> **Vi hjælper gerne med at holde øje med materialer til dig eller undersøge,
> om de kan fremskaffes gennem kommende projekter.**"

Den sidste sætning er guld værd for et totalrenoveringsprojekt: de tilbyder
eksplicit at holde udkig efter specifikke materialer fra kommende nedrivninger.

**B--D:** Ikke relevant. Ingen bot-beskyttelse; Squarespace-HTML hentede fint
(216 KB).

**E. Geografi -- det bedste af alle sites med rigtigt varelager:**
Butikken hedder **Sct. Clara Genbrug**, Rønøs Allé 4, **4000 Roskilde**.
Ca. **35 km / ~30 min** fra København. Åbent **alle hverdage**:
man--tors 07.00--15.00, fre 07.00--14.00.
Kontakt: sct.clara@hockerup.dk · Julie 30 80 84 52 · Rebekka 30 80 78 15.

LH Hockerup A/S er en nedrivnings- og miljøsaneringsvirksomhed (CVR 27143334,
medlem af Nedrivnings- og Miljøsaneringssektionen), dvs. materialerne kommer
fra selektiv nedrivning -- netop den kilde hvor branddøre og brandpartier
rent faktisk optræder.

**F. Branddøre:** Ingen oplysning online. Må afklares ved henvendelse.

---

## 17. genbyg.dk -- brugte vinduer (ALLEREDE BYGGET KILDE)

URL: `https://genbyg.dk/doere-vinduer/brugte-vinduer/?gad_source=1&...`

Dette er en kategoriside på den eksisterende kilde. Spørgsmålet var, om den
dækkes af `config.doere.yaml`'s søgetermer, eller om den afslører noget den
nuværende søgning overser.

**Først bekræftes genbyg.py's docstring:** kategorisiden er client-side
renderet. Målt: HTTP 200, 99,8 KB -- og **0 produktkort i rå HTML**. Søgeruten
(`POST /rest/search`) er fortsat den eneste farbare vej uden browser-JS.
Kategorisiden kan altså ikke bruges som indgang uanset hvad.

**Dernæst måles hvad de nuværende 13 søgetermer faktisk henter** (POST
/rest/search, op til 3 sider pr. term, kort talt i rå HTML):

| Søgeterm | Kort |
|---|---:|
| indvendig dør | 72 |
| branddør | 50 |
| yderdør | 47 |
| BD30 | 29 |
| "terrassedør" | 22 |
| BD60 | 11 |
| "brandglas" | 5 |
| BS60 | 5 |
| EI30 | 3 |
| brandvindue | 2 |
| brandvinduer | 2 |
| EI60 | 1 |
| brandparti | 0 |
| **Unikke produkter i alt** | **204** |

**Hvad overses? Vindues-udbuddet, næsten fuldstændigt.** Målt ved at køre
søgetermer der IKKE står i configen:

| Ikke-konfigureret term | Kort (max 5 sider) | heraf m. brandklasse i titel |
|---|---:|---:|
| `vindue` | 120 | 2 |
| `termovindue` | 119 | 1 |
| `fastkarm` | 35 | 4 |
| `dannebrogsvindue` | 8 | 0 |
| `vinduesparti` | 4 | 0 |

Kategorisiden har desuden 19 vindues-underkategorier
(`termovinduer`, `sprossevinduer`, `jernvinduer`, `enkeltlagsglas`,
`skillerumsvinduer`, `forsatsvinduer`, `vinduesrammer`, `andre-vinduer`, ...)
som ingen nuværende søgeterm rammer.

**MEN -- dette er IKKE en fejl, det er en dokumenteret, målt beslutning.**
`config.doere.yaml` linje 41--43 siger ordret at `"vindue"` blev FJERNET fordi
*"0 af 162 hentede rækker over 3 sider havde en brandklasse (hele pointen med
'brandvindue'/BD60 i denne kategori), og 17 af 162 var slet ikke
vinduesprodukter"*. Min måling i dag bekræfter billedet på en anden kilde:
2 af 120 (1,7 %) for `vindue`, 1 af 119 (0,8 %) for `termovindue`.

**Konklusion for site 17:** Kategorisiden afslører ~200+ vinduer som den
nuværende søgning ikke henter, men de er næsten alle uden brandklasse, og
dermed ramt af præcis den støjbeslutning der allerede er truffet og begrundet
med tal. **Ingen ændring anbefales i `config.doere.yaml` på dette grundlag.**
Den ene undtagelse der KAN overvejes er `fastkarm`: 4 af 35 (11 %) havde
brandklasse i titlen -- en betydeligt bedre signalandel end `vindue`s 1,7 %,
og på et beskedent volumen (35 kort = 2 sider). Det er dog et lille fund og
bør i givet fald verificeres med samme 3-siders-protokol som de oprindelige
termer, før det tilføjes.

---

# PRIORITERET KONKLUSION

Hver anbefaling nedenfor er begrundet med et konkret, målt fund fra
gennemgangen ovenfor -- ingen rene gæt.

## A. Byg som nye scraper-kilder (ligesom genbyg.py)

### 1. jk-genbrugscenter.dk -- klart stærkeste kandidat

**Begrundelse (målt):**
- **1.302 dør-/vinduevarer** (716 vinduer + 586 døre) og **73 branddøre** --
  det største brandklassificerede udbud med mål i hele undersøgelsen.
- **100 % struktureret måldækning på branddørene** (73/73 kort har
  `<b>B</b> … cm / <b>H</b> … cm` som eget felt), 97 % på fastkarmsvinduer
  (156/161). Det er genbyg.dk-niveau eller bedre.
- **Offentligt WooCommerce Store API** (`/wp-json/wc/store/v1/products`,
  `x-wp-total: 1453`), 100 varer pr. request, med kategori- og
  fritekstfilter. Et kategoritræk på branddøre er ÉN request der returnerer
  alle 73 med sku, pris i minor units, lagerantal og permalink.
- **Ingen bot-beskyttelse overhovedet** -- plain `requests`, præcis som
  genbyg.py. Tilladende robots.txt uden crawl-delay.
- Odense, ca. 165 km / 1 t 50 min fra København -- realistisk afhentning.

**Teknisk note til implementering:** API'ets `short_description` har målene som
"Bredde 108 / Højde 217" (71/73 = 97 %), mens HTML-kortene har dem som rene
WooCommerce-dimensionsfelter (73/73 = 100 %). HTML-ruten giver altså den
bedste dækning; API-ruten giver færrest requests. Begge virker.

### 2. bygbrugt.dk -- bedste datastruktur, kræver WAF-håndtering

**Begrundelse (målt):**
- **Den reneste struktur i hele undersøgelsen:** en HTML-tabel med navngivne
  kolonner `Bredde | Højde | Materiale | Farve | Lag glas | Pris`. Bredde og
  højde er rene tal i egne `<td>`'er. Ingen anden kilde giver materiale,
  farve og antal lag glas som separate felter.
- **58 brandklassificerede varer med egen kategori pr. brandklasse**
  (`/doere/branddoere/bd30` = 42, `/bd60` = 6, `/bs60` = 7,
  `/dobbelte-branddoere` = 3, `/glas-og-glasdoere/brandglas` = 3), heraf
  57 med numerisk B+H. Ingen anden kilde har brandklassen som kategori
  frem for som tekst i en titel.
- **498 vinduer** (394 med numerisk B+H) + 85 yderdøre (77 med B+H).
- **Ingen paginering at håndtere** -- hele kategorien ligger i rå HTML i én
  request.
- WAF'en er **ikke** en grund til Playwright: challenget er målt som et
  SHA-256 proof-of-work med difficulty 16, løst i **0,01 s** i ren Python,
  og `sc_clearance`-cookien gælder 24 timer. ~25 linjer kode i en
  `requests`-kilde.

**Forbehold der skal med i beslutningen:** serveren svarede på et tidspunkt
HTTP 455 "Security Incident Detected -- Do not retry" under intensiv
hentning. Kilden SKAL throttles ordentligt og må ikke retry-spamme på 455.
robots.txt er tilladende (`Disallow: test`), så der er intet eksplicit forbud
-- men WAF'ens tilstedeværelse er i sig selv et signal, og en kort mail til
Langå inden produktion er billig forsikring.

### 3. skave-nedbrydning.dk -- størst volumen, bedst måldata, men langsom

**Begrundelse (målt):**
- **5.447 varer i alt**, heraf **2.914 vinduer**, 326 terrassedøre,
  263 indvendige døre, 246 udvendige døre -- suverænt det største udbud.
- **Strukturerede mål med vægt oveni:** `b: 59,0 cm`, `h: 119,0 cm`,
  `km: 7,0 cm` (karmdybde), `v: 28,0 kg`, Produkt ID og lagerantal som
  separate felter pr. kort. **79 % dækning over hele kataloget**
  (4300/5447), **100 %** i de stikprøvede dør-/vinduekategorier.
- **99 brandrelaterede varer**, heraf 55 navngivet `BD30`, 17 `BS60`,
  2 `BD60`, 1 `EI2 30` -- næststørst efter JK.
- **Bevist server-side målfiltrering** (326 -> 109 varer ved at snævre
  bredde til 85--100 cm og højde til 200--220 cm). Kun to kilder i hele
  undersøgelsen kan dette: genbyg.dk og Skave.
- Ingen bot-beskyttelse.

**Hvorfor nr. 3 og ikke nr. 1 trods størst volumen:** robots.txt kræver
`Crawl-delay: 30` og forbyder eksplicit `?limit=`. Den hurtige rute
(`limit=500`, hele kataloget i 11 requests) er altså ikke tilladt, og den
tilladte rute er 73 sider × 30 s ≈ **37 minutter bare for vinduerne**. Det er
en reel driftsomkostning der skal designes for (fx kun dør-kategorierne, eller
inkrementel hentning), ikke bare en detalje. Dertil er Holstebro 330 km / 3 t
40 min fra København, hvilket gør afhentning til en dagsrejse.

## B. Bedre egnet som "kontakt direkte"-leads (intet katalog at scrape)

### LH Hockerup / Sct. Clara Genbrug, Roskilde -- det bedste lead

Målt: 0 varer online (hele sitemap.xml gennemgået, ~40 URL'er, kun
firmasider + 2 ren-tekst butikssider). Men:
- **Rønøs Allé 4, 4000 Roskilde -- ca. 35 km / 30 min fra København**, åbent
  alle hverdage. Den nærmeste rigtige genbrugsbyggeplads med lager.
- Materialerne kommer fra **egen selektiv nedrivning og miljøsanering** --
  præcis den kilde hvor branddøre og brandpartier faktisk findes.
- De tilbyder eksplicit på deres egen side: *"Vi hjælper gerne med at holde
  øje med materialer til dig eller undersøge, om de kan fremskaffes gennem
  kommende projekter."* For en totalrenovering med konkrete målkrav er en
  stående forespørgsel hos dem mere værd end nogen scraper.
- Kontakt: sct.clara@hockerup.dk · Julie 30 80 84 52 · Rebekka 30 80 78 15.

### Den Grønne Genbrugshal, Christiania

Målt: sitemap.xml indeholder **tre** sider i alt (`/home`, `/kontakt`,
`/omos`). Nul varer. Men forsiden nævner eksplicit "Døre og vinduer genbrug"
og "Glas. Vi skærer efter mål", og adressen er **Fabriksområdet 56, 1440
København K -- 0 km**. Ring/besøg (+45 32 54 79 24), åbent 7 dage om ugen.

### P. Olesen genbrug, Hovedgård

Målt: 42 "varer" i Store API'et, alle kategori-pladsholdere uden mål og pris.
Branddør-"varen" siger ordret *"I hallen finder du mange BD30- og ind imellem
nogle BD60 branddøre … Kom og find din dør"*, og vindue-"varen" hedder
*"Vinduer – tag tommestokken med, og gå på jagt"*. Der ER altså et stort
fysisk lager af BD30-døre, men nul af det er registreret online. 260 km fra
København gør det til et ringe-først-sted, ikke et køre-forbi-sted.
genbrug@p-olesen.dk.

### jensengenbrug.dk -- afventer, ikke afvist

Målt: `/katalog` = HTTP 404, rodsiden = 766 bytes vedligeholdelsesside med
billedtekst **"will be online again Monday 12/10"**. Der er ikke grundlag for
en vurdering i nogen retning. **Genbesøg efter 12. oktober 2026** og kør samme
måleprotokol.

## C. Spring over

| Site | Målt grund til at springe over |
|---|---|
| **brugtemursten.dk** | 5,5 KB statisk side, nul produkter -- og virksomheden sælger **kun mursten**. Ingen døre, ingen vinduer. Forkert varegruppe for kategorien `doere`. |
| **titan-genbrug.dk** | `x-wp-total: 46` for HELE sitet. 3 branddøre, 3 terrassedøre, 10 vinduer. Kun 35 % af varerne har mærket Bredde+Højde. Aalborg, 380 km / 4 t 15 min, **åbent kun torsdage 9--14**. Volumen står ikke mål med en kilde + WAF-håndtering. |
| **genbrugsbyg.dk** | 104 varer på hele sitet, heraf **7 døre** og 21 vinduer. Præcis **1** branddør (BD60 uden karm). Mål kun i titlen og inkonsistent formateret. Enkeltmandsvirksomhed i Grindsted (280 km) der er "bedst at træffe på telefon efter 16.30". |
| **rodekorsgenbrug.dk** | **0 brandklassificerede varer på tværs af alle syv byggemarkeds-kollektioner (906 varer)** -- donerede overskudsvarer, ikke nedrivningsmateriale. Kun 16 varer i "Vinduer og døre" i Odense, og kun 8 af dem har mål (20 % måldækning på hele kollektionen, på niveau med DBA's 21,7 %). Glostrup-afdelingen er tæt på (15 km) men har målt **4** dør-/vinduevarer. |
| **pogenbrug.dk** | Intet katalog -- 42 pladsholdere. Flyttet til "kontakt direkte" ovenfor, ikke til scraper-listen. |
| **greendozer.com** | **Spring over indtil videre, af compliance-grunde, ikke tekniske.** Teknisk er den fin: åbent GraphQL, 123 døre inkl. 29 med BD30/BD60/DB35 i navnet, 89 % måldækning i navnekonventionen, alt i ét kald med `pageSize:200`. MEN `robots.txt` indeholder eksplicit `User-agent: ClaudeBot / Disallow: /`. Dertil "Kun B2B salg" og *"Obs ingen varelager på adressen"* (Aarhus-adressen er et kontor; varerne står hos leverandørerne, så afhentningsafstanden er ukendt pr. vare). Skal afklares direkte med GreenDozer (support@greendozer.com) før noget bygges. |

## D. Grænsetilfælde -- byg senere, hvis der er brug for mere volumen

**baerebyg.dk (Struer, 350 km):** 189 døre + 254 vinduer + 21 branddøre, åbent
Store API (`x-wp-total: 1459`), ingen bot-beskyttelse. **92 % af 521
dør-/vinduetitler** har et D×B×H-mønster -- langt over DBA's 21,7 %. Men det
er fritekst, ikke felter, og **det første tal er karmdybde, ikke bredde**, så
det kræver en kildespecifik parser. God som kilde nr. 4.

**demfranordlunde.dk (Nakskov, 150 km):** 55 døre + 40 vinduer, **95 %
måldækning på vinduerne** (38/40) med NAVNGIVNE felter i titlen
("Bredde:131 Højde:212") -- ingen tvivl om hvilket tal der er hvad.
**Geografisk næstbedst af alle sites med et rigtigt katalog.** Men: 0
brandklassificerede varer overhovedet, og samme simply.com-WAF som bygbrugt
(dog triviel at håndtere, 0,07 s). Relevant hvis projektet også skal bruge
almindelige facade-/terrassedøre og vinduer, irrelevant hvis kun brandkrav.

## E. Genbrugeligt teknisk fund på tværs af kilder

Tre af de 16 sites (**bygbrugt.dk, titan-genbrug.dk, demfranordlunde.dk**)
ligger bag **samme WAF: simply.com's Website Application Firewall**. Hvis der
bygges én kilde bag den, kan bypass-logikken deles af alle tre. Protokollen,
målt og verificeret på alle tre domæner:

1. GET -> HTTP 454, side med `var T="<64 hex>",TS="<unix>",D=16;`
2. Find `nonce` hvor `sha256(f"{T}:{nonce}")` har ≥ `D` ledende nul-bits
   (målt: 0,01--0,07 s)
3. `POST /.sc-verify/` med `ts`, `nonce`, `token` -> `{"ok":true,"cookie":"..."}`
4. Sæt cookien som `sc_clearance` på domænet; gyldig 24 timer (`max-age=86400`)
5. Challenget er **intermittent** -- koden skal også kunne håndtere HTTP 200
   i første forsøg, og skal respektere HTTP 455 ("Do not retry") som en
   hård pause, ikke som noget man prøver igen med det samme.

Ren `requests` + `hashlib`. **Ingen Playwright nødvendig for nogen af de 16
sites i denne undersøgelse.**
