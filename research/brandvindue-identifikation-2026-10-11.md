# Identifikation af brandvinduer i genbrugs-byggemateriale-annoncer

**Skrevet af:** Sonnet 5 (ikke Opus -- den planlagte Opus-research ramte den
ugentlige API-grænse undervejs og måtte afbrydes, se note nederst). Alt
mærket **MÅLT** er verificeret direkte mod live data i dette projekt. Alt
mærket **FAGLIGT SKØN** er almindelig byggebranche-/brandsikringsviden jeg
vurderer rimeligt sikker, men IKKE har verificeret med en frisk websøgning
denne gang -- behandl den kategori som "værd at tjekke", ikke som bevist.

## A. Kendte brandglas-/brandvinduessystem-mærker

**MÅLT (jk-genbrugscenter.dk, 1.453 varer gennemsøgt):** kendte europæiske
brandglas-mærker (Pyrobel, Pyran, Contraflam, Vetrotech, Pyrodur, Promat,
Swissflam, Pilkington Pyrostop) gav **0 træf** i hele kataloget, bortset fra
"Pyrobel" i 2 allerede-korrekt-kategoriserede branddøre (ikke skjulte
vinduer). Sælgere på denne type genbrugsmarked nævner altså praktisk talt
ALDRIG det tekniske mærkenavn på selve glasset/systemet -- kun en kort
produktbetegnelse ("Brandglas BD30") eller slet intet brandord.

**FAGLIGT SKØN:** de mærker der blev testet ER reelle, etablerede
brandglas-/brandvinduesmærker i den europæiske byggebranche (Pyrobel =
AGC Glass Europe, Pyrostop/Pyrodur = Vetrotech Saint-Gobain, Contraflam =
samme producentgruppe, SCHOTT Pyran = tysk producent). At de ikke dukker op
i sælgernes egne tekster betyder IKKE at de er irrelevante -- det betyder at
**mærkenavn ikke er en brugbar søgestrategi på dette marked**, fordi de
sjældent skrives i en brugt-annonce. Konklusion: byg IKKE en mærke-ordliste
ind i scraperen -- den vil give nær-nul gevinst, baseret på det ene site vi
har målt grundigt.

## B. Andre tekstlige signaler uden "brand"-ordet eller et BD/EI-tal

**MÅLT (bygbrugt.dk, 2026-10-10):** sitets EGEN tabel-struktur for
kategorien "glas-og-glasdoere/brandglas" bruger forkortelsen **"E30"/"E60"**
i stedet for "EI30"/"EI60" i sin strukturerede "BD"-kolonne -- en reel,
dokumenteret variant af klassebetegnelsen, som hverken vores
`_FIRE_CLASS_PATTERN` eller `_BRAND_WORD` fangede, FØR denne kildes egen
kategori-tildeling blev brugt som en eksplicit, uafhængig signalkilde (se
`sources/bygbrugt.py`'s håndtering af denne kategori). Dette er det
konkrete bevis for at "brand-ord eller tal" IKKE er udtømmende -- der findes
mindst én reel, dokumenteret forkortelsesvariant i omløb.

**FAGLIGT SKØN, ikke målt:** andre tænkelige varianter en sælger kunne
bruge uden hverken "brand" eller et tal: "modstandsdygtig mod brand i X
minutter" (udskrevet i stedet for forkortet), "fra erhvervsbygning" / "fra
trappeopgang" / "fra brandcelle" (oprindelsessted antyder funktion, men
beviser intet alene), eller blot et foto af et typeskilt UDEN at teksten
derfra er gentaget i selve annonceteksten (se E).

## C. Fysiske/strukturelle signaler (sandsynligheds-indikatorer)

**MÅLT, HYPOTESE AFKRÆFTET:** brugerens egen hypotese ("brandvinduer gemmer
sig under fastkarm, da det er vinduer der ikke kan åbnes") blev testet
direkte mod jk-genbrugscenter.dk's fulde "Fastkarmsvindue"-kategori (161
varer). **Ingen korrelation fundet** -- samtlige undersøgte beskrivelser
nævner udelukkende "lavenergiglas" (energirude) med almindelige
vinduesmærker (Rationel, Velfac, JNA), aldrig brandrelateret tekst. Fastkarm
betyder på dette marked næsten altid "billigt, ikke-åbningsbart
standardvindue" (fx til et udhus eller en kælder), ikke "brandadskillelse".

Dette udelukker IKKE at korrelationen kan holde bedre på ANDRE sites (vi har
kun testet ét site grundigt), eller i den bredere byggebranche generelt
(bygningsreglementets krav til brandadskillelse betyder i praksis ofte en
fast, ikke-åbningsbar rude i en brandcelle-væg) -- men som SELVSTÆNDIGT
filter på tværs af et sekundhåndsmarked er den for svag til at bruge alene.

**FAGLIGT SKØN (ikke målt her):**
- **Glastykkelse/lag:** brandglas er typisk lamineret med flere lag og en
  brandhæmmende mellemlag-gel, ofte tykkere end en tilsvarende energirude.
  Bygbrugt.dk har faktisk en "Lag glas"-kolonne vi allerede opsamler
  (`description_parts`) -- et usædvanligt højt lagtal (3+) KUNNE være et
  svagt signal, men er ikke testet mod kendte brandglas-eksempler endnu.
- **Vægt:** skave-nedbrydning.dk er den eneste kilde i hele undersøgelsen
  der leverer vægt pr. vare (se `sources/skave_nedbrydning.py`) -- et
  usædvanligt tungt vindue for sine mål KUNNE indikere lamineret
  brandglas, men der findes intet referencedatasæt i dette projekt endnu
  til at kalibrere en tærskel.
- **Pris:** et ægte certificeret brandvindue er typisk dyrere end et
  tilsvarende almindeligt vindue ny-pris, pga. specialproduktion og
  certificering -- men på et BRUGT marked er prisen domineret af alder,
  stand og sælgers eget skøn, ikke oprindelig nypris, så dette signal er
  sandsynligvis for støjende til at bruge alene.

**Samlet vurdering af C:** ingen af disse strukturelle signaler er stærke
nok til at stå alene. De kunne i teorien kombineres til en "mistænkelig,
men ikke bekræftet"-scoring, men uden et kendt facit-datasæt at kalibrere
imod vil en sådan model gætte lige så meget som den hjælper.

## D. Forslag til udvidet matchstrategi -- og en ærlig vurdering af gevinsten

**Konkret, lavrisiko-tilføjelse:** udvid den eksisterende
`_FIRE_CLASS_PATTERN`/`_BRAND_WORD`-logik i `doere_normalize.py` til også at
acceptere bogstavet "E" alene (uden "I") foran et klassetal, som et
dokumenteret alias for "EI" -- MÅLT fund fra bygbrugt.dk's egen "BD"-kolonne
("E30"/"E60"). Risiko: lav, da "E" + tocifret tal i en dør-/vindueskontekst
sjældent betyder noget andet. Forventet gevinst: lille i absolutte tal (kun
observeret på ét site indtil videre), men fjerner en kendt, dokumenteret
fejlkilde.

**IKKE anbefalet lige nu:** en vægt-/tykkelse-/lag-glas-baseret
sandsynligheds-scoring (se C). Uden et kendt facit-datasæt (fx 20-30
bekræftede brandvinduer med deres fulde mål/vægt/lag, sammenlignet med 20-30
bekræftede ikke-brandvinduer) er en sådan model ren gætteri klædt ud som
videnskab -- det ville modsige projektets egen husstil om kun at bruge
MÅLTE tærskler. Forslag: vent til der er indsamlet nok bekræftede
brandvinduer på tværs af kilderne (nu 17, se status nedenfor) til at denne
kalibrering giver mening, fx ved 50+.

**Ærlig konklusion om den samlede dækning:** det STØRSTE, allerede
dokumenterede tab i dette projekt var IKKE manglende data fra sælgerne --
det var to rene KODEFEJL, begge fundet og rettet i denne session:
1. Et brandord uden tal ("Indvendigt brandvindue") blev ikke genkendt som
   et fire-signal uden et ledsagende BD/EI-tal.
2. En dør der nævner "vindue" i forbifarten blev fejlagtigt bøttet som et
   vindue i stedet for en dør.
Efter disse to rettelser gik det bekræftede antal brandvinduer fra 2 til
17 (jf. den løbende status i Turso). Det tyder på at vores EKSISTERENDE
tekstbaserede detektion (brandord + klassetal) allerede fanger langt
størstedelen af det der reelt findes i sælgernes egen tekst -- den
resterende, umålte gruppe er sandsynligvis mindre end man skulle tro ud fra
hvor få brandvinduer der oprindeligt var synlige.

## E. Verifikation af et usikkert kandidat-fund

Uden fysisk besøg er den bedste praktiske metode et **typeskilt-/mærkat-
tjek på selve glasset**: brandklassificeret glas bærer i Danmark/EU typisk
et lille, permanent mærke i ÉT hjørne af ruden (ofte ætset eller et lille
klistermærke) med producent, klasse (fx "EI30") og godkendelsesnummer --
samme idé som en CE-mærkning. Konkret, billig handling for dette projekt:

- Når en annonce allerede HAR et thumbnail (se `image_url`-feltet, allerede
  opsamlet fra dba.dk/jk-genbrugscenter.dk), er der reelt ingen måde at
  læse et så småt mærke fra et thumbnail i dashboardet -- det kræver at
  brugeren selv åbner det fulde billede og zoomer.
- Forslag (ikke implementeret her, kun en idé til senere): en "formodet
  brandvindue, ikke bekræftet"-markering i dashboardet for annoncer hvor
  et SVAGT signal findes (fx kun "fastkarm" + højt lagtal glas, uden et
  egentligt brandord), med en konkret opfordring til brugeren om selv at
  spørge sælgeren "er der et EI/BD-mærke synligt i et hjørne af glasset?"
  før køb -- genbruger samme mønster som `spoergsmaal_til_saelger`-feltet,
  der allerede findes i klassifikationen.

## Prioriteret anbefaling

1. **Gør nu (lav risiko, lille men reel gevinst):** tilføj "E" som alias
   for "EI" i `_FIRE_CLASS_PATTERN`, dokumenteret af bygbrugt.dk's egen
   "BD"-kolonne.
2. **Gør ikke nu:** en vægt-/tykkelse-baseret sandsynligheds-model (C)
   -- intet facit-datasæt at kalibrere imod endnu.
3. **Overvej senere, når der er flere bekræftede brandvinduer at
   kalibrere imod (fx 50+):** en "formodet, ikke bekræftet"-dashboard-
   markering med et opfølgende spørgsmål til sælger (E).
4. **Den reelle gevinst hidtil kom fra at RETTE kode, ikke fra at UDVIDE
   søgningen** -- hold dette for øje før der investeres mere tid i nye
   signaler: tjek først om der er flere lignende klassifikationsfejl i den
   eksisterende logik, før der bygges nyt.

## Note om denne undersøgelses begrænsning

Den oprindeligt planlagte, bredere Opus-drevne research (bl.a. en grundigere
websøgning efter danske producenters egne brandvinduesserier, og en mere
systematisk gennemgang af sælger-sprogbrug på tværs af flere sites) blev
afbrudt af en ugentlig API-grænse og kunne ikke gennemføres i denne omgang.
Dette dokument er derfor bygget på egne direkte målinger (afsnit A-C's
MÅLT-dele) plus almindelig fagkendskab (afsnit A-C's FAGLIGT SKØN-dele,
IKKE web-verificeret denne gang) -- ikke en udtømmende markedsundersøgelse.
Overvej at genbesøge dette dokument, hvis der senere er adgang til en
grundigere research-runde.
