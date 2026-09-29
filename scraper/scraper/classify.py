"""Additiv scoring-model for sikkerhedsstøvsugere -- IKKE en percentil-baseret
klassifikation (modsat PASPEAKERS' classify.py). Specen beder eksplicit om
hårde krav (porte) + bløde krav (±point), mappet til køb nu/se nærmere/afvis --
se agent-promptens "KRAV TIL EN GODKENDT TRÆFFER" og "PRISLOFTER"-sektioner.

Beslutninger denne fil selv lægger oven på specens tekst (dokumenteret her så
brugeren kan justere via config.yaml i stedet for at skulle læse kildekode):

1. "Regn 700-900 kr. oveni til nyt H-filterelement PÅ ENHVER BRUGT MASKINE"
   tolkes som: læg et fast beløb (config: filter_replacement_estimate_dkk,
   default 800) oveni landed_price_dkk FØR sammenligning med prislofterne,
   MEDMINDRE annoncen selv nævner et nyt/nyligt skiftet filter (nyt_filter).
2. "Overskrid aldrig 70% af aktuel nypris" tolkes som en HÅRD afvisning
   (ikke blot et minuspoint) når modellens kendte nypris i models.py gør
   det muligt at tjekke -- ukendt nypris betyder blot at denne ene port
   ikke kan håndhæves, IKKE at annoncen automatisk godkendes.
3. "Køb ≤ X" i PRISLOFTER-sektionen tolkes som et hårdt loft (over = afvis,
   ikke "se nærmere") -- "god handel ≤ Y" er den lavere tærskel for hvornår
   den effektive pris alene er stærk nok til (sammen med opfyldte hårde
   krav) at berettige "køb nu" uden yderligere due diligence.
4. Batterimaskiner og ubekræftet M-klasse (asbest IKKE udelukket med
   sikkerhed) kan aldrig blive "køb nu", uanset score/pris -- loftet er
   "se nærmere" (spec: "batterimaskiner kun som sekundært fund").
"""

from __future__ import annotations

# Faste spørgsmål til sælger -- spec: "generér ALTID ved 'se nærmere'".
SELLER_QUESTIONS = [
    "Billede af typeskiltet bag på eller under motorhovedet",
    "Står der L, M eller H på typeskiltet eller advarselsmærkaten?",
    "Hvornår er filterelementet sidst skiftet, og er det originalt?",
    "Giver flowalarmen lyd, når slangen dækkes til?",
    "Har maskinen kørt asbest?",
    "Medfølger der sikkerhedsfilterposer?",
    # Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A): asbestmærkningen
    # er SKU-specifik, ikke serie-bred. Samme modelnavn kan dække både en
    # asbestmærket og en umærket varenummer-variant (Nilfisk Attix 33-2H: kun
    # 107412183 "ASBES" og 107419012 "BG BAU ASBEST" er mærkede, mens
    # 107412184 IKKE er det) -- og producentens egen serietekst om
    # asbestcertificering står også på maskiner der IKKE må køre asbest.
    # Varenummeret er derfor det eneste, sælgeren kan oplyse, som faktisk
    # afgør spørgsmålet.
    "Hvilket varenummer/art.nr. står der på typeskiltet? (asbestmærkningen er "
    "SKU-specifik, ikke serie-bred -- samme modelnavn findes både mærket og umærket)",
]

_PRICE_CATEGORY_COMPACT_H = "kompakt_h"
_PRICE_CATEGORY_LARGE_H = "stor_h"
_PRICE_CATEGORY_M = "m_klasse"


def _price_category(dust_class: str | None, container_l: float | None) -> str | None:
    if dust_class == "M":
        return _PRICE_CATEGORY_M
    if dust_class == "H" and container_l is not None:
        # RETTET 2026-09-29: den øvre grænse for "kompakt" var 35 l, og specens
        # to intervaller (25-35 og 40-75) efterlod derfor et HUL på 36-39 l.
        # Hullet var tomt indtil stovsuger-modeloversigt2.md's afsnit 7A/7C
        # rettede to modellers volumen til netop det interval: Nilfisk Attix
        # 44-2H IC (44 -> 37 l) og Hilti VC 40H-X (30 -> 36 l). Uden denne
        # rettelse ville begge falde ud i category=None, dvs. HVERKEN kunne
        # afvises på prisloft ELLER nogensinde blive "køb nu" -- en maskine
        # ville stille miste sin prisport, fordi dens volumen blev mere
        # korrekt. Hullet lukkes opad mod "kompakt", ikke nedad mod "stor",
        # fordi kompakt-kategorien har det LAVESTE købsloft (3.500 vs. 5.000
        # kr.) -- dvs. det konservative valg, jf. husets linje om hellere at
        # afvise for meget end at godkende for meget.
        if 25 <= container_l < 40:
            return _PRICE_CATEGORY_COMPACT_H
        if 40 <= container_l <= 75:
            return _PRICE_CATEGORY_LARGE_H
    return None


# ---------------------------------------------------------------------------
# KANDIDAT-STIGEN (ny 2026-09-29, Opus-review af intake/validering).
#
# Brugerens opdrag: "For alle datakilder bør vi ved indtag løsne kravet om
# kendte mærker uden modelnummer ... og så skal vi bygge vores egen
# datavalidering i vores ende. Få Opus til at foreslå en række metoder og
# teste hvad der giver resultater."
#
# Den gamle mekanik var ÉN binær port: known_brand_mentioned (= kendt mærke
# NÆVNT **og** et modelnummer-agtigt tal, se normalize.has_model_token).
# Bestod annoncen ikke den, blev den afvist. Porten blev indført bevidst
# 2026-09-20 efter at brugeren manuelt diskvalificerede "Bosch støvsuger"/
# "Nilfisk støvsuger" -- annoncer uden noget som helst at verificere -- og
# den skal derfor IKKE bare slås fra. Den erstattes i stedet af en stige med
# fire trin, hvor det gamle trin er bevaret som trin 3.
#
# Alle fire trin er målt mod 808 RIGTIGE annoncetitler: 707 live-rækker
# hentet fra Turso via Worker-API'et, plus 101 friske fund fra brede
# probe-søgninger mod klaravik.dk/auktionshuset.dk/dba.dk/retrade.eu.
# Nøgletallet er de 462 live-rækker der i dag er afvist med præcis
# "intet identificerbart signal" -- det er den pulje en løsning skal hente
# reelle fund op af UDEN at hente resten med.
#
#  Trin 1  sikkerhedssuger-vokabular  ->  3 af de 462, ALLE TRE reelle:
#          'Asbestsauger' (1.119 kr.), 'Bosch Asbest-Sauger
#          Industriestaubsauger' (2.798 kr.), 'Asbest Sauger
#          Sicherheitssauger H' (3.730 kr.). Alle tre er tyske; vi SØGTE
#          aktivt efter dem ("Asbestsauger" er et af vores syv primære
#          søgeord) og afviste dem så selv.
#  Trin 2  klassebogstav + anker      ->  2 af de 462 ('Starmix H tør og våd
#          støvsuger' 1.500 kr., 'Baier BSS 608H våd-/tørsuger 1200W'
#          4.300 kr. -- sidstnævnte er endda en whitelistet model), og 12 af
#          de 101 friske probe-fund (seks RONDA H-maskiner, 'Starmix ISC
#          1625 H', 'Bona støvsuger klasse H . Dc 25', 'Starmix Vaccufix H').
#          Målt præcision på hele korpus: 30 reelle ud af 31 fund (97 %).
#  Trin 3  mærke + modelnummer        ->  uændret gammel opførsel.
#  Trin 4  mærke + industri-kategori  ->  det egentlige "løsn kravet".
#          23 fund på hele korpus, heraf ~10 reelle kandidater, INKLUSIVE
#          brugerens eget eksempel: Klaravik-annoncen 'Industristøvsugere
#          Electrostar Starmix IS 2 styk' (2.200 kr.), som ikke rammes af
#          nogen af de tre trin ovenfor (intet klassebogstav, intet
#          modelnummer, intet asbest-ord).
#
# TO VÆRN PÅ TRIN 4, fordi det er det svageste og bredeste:
#  (a) Det kræver INDUSTRIAL_CATEGORY_PATTERN ("industristøvsuger",
#      "Industriesauger", "Werkstattsauger", "våd-/tørsuger", ...) og IKKE
#      det bare "støvsuger"/"dammsugare". Den brede variant blev også målt:
#      38 fund hvoraf kun ~3 var relevante -- resten var præcis den støj
#      porten oprindelig blev bygget for ('Bosch dammsugare rosa med
#      teleskoprör', 'Nilfisk Compact dammsugare röd', 'Bosch støvsuger',
#      'Nilfisk støvsuger'). Den smalle variant giver ~10 af 23.
#  (b) En PRISBUND (config: minimumspris_svagt_signal_dkk). Målt på de 23
#      fund fra trin 4 ligger samtlige reelle kandidater på 1.050 kr. og
#      opefter, mens fem af de seks støj-fund ligger under 800 kr.
#      ('Nilfisk industristøvsuger gammel model' 75 kr., 'Retro Nilfisk GSD
#      støvsuger industristøvsuger' 100 kr., 'Nilfisk GSD industristøvsuger
#      grå' 350 kr., 'Numatic industristøvsuger med vogn og rør' 450 kr.,
#      'Kärcher Professional våt- och torrdammsugare' 630 kr.). Bunden er
#      sat til samme beløb som filter_replacement_estimate_dkk, og den
#      begrundelse er selvbærende: en maskine der koster mindre end det
#      H-filterelement man er NØDT til at sætte i den, er ikke en seriøs
#      kandidat. Modellen med den laveste kendte nypris i models.py (Metabo
#      ASA 30 H PC, 2.349 kr.) understøtter samme størrelsesorden.
#      FEJLTILSTAND, bevidst accepteret: bunden ville afvise et ægte røverkøb
#      som 'Flex-industristøversuger VCE44-AC H-klasse' til 500 kr. (set i
#      live-data) -- men netop den annonce har et klassebogstav og fanges
#      derfor allerede af trin 2, hvor prisbunden IKKE gælder. Bunden rammer
#      kun det svageste trin.
#
# BEVIDST IKKE BYGGET (metoder der blev testet og målt UTILSTRÆKKELIGE på
# netop disse data -- se README for den fulde gennemgang):
#  * Watt/vægt-heuristik: husholdningsstøvsugere i korpus'et kører 1.300-2.000
#    W ('1300w bil dammsugare', 'Siemens dammsugare 1800W') -- præcis samme
#    interval som industrimaskinerne. Adskiller ikke.
#  * Spec-tæthed (flow/filterklasse/volt sammen): 4 fund på 808 titler, og et
#    af dem var en askestøvsuger. Metoden forudsætter en BESKRIVELSE, og
#    ingen af de otte kilder leverer en -- alle sources/*.py sætter
#    `"description": ""`.
#  * Beholdervolumen + industriord: 5 fund på 808, ingen diskriminerende
#    kraft (titler oplyser sjældent liter).
#  * Kilde-leveret kategori/brødkrumme: ingen af de otte kilder opsamler den
#    i dag; det kræver ny scraping-kode pr. kilde, ikke en filter-ændring.
# ---------------------------------------------------------------------------
_KANDIDAT_NOTER = {
    "sikkerhedssuger-vokabular": (
        "annoncen markedsfører maskinen som asbest-/sikkerhedssuger, men intet "
        "modelnavn matcher models.py -- bed om billede af typeskiltet (asbestbrug "
        "forudsætter H-klasse, så påstanden er kontrollerbar)"
    ),
    "klassebogstav": (
        "et klassebogstav (H/M) optræder i annoncen uden at et modelnavn kunne "
        "bekræftes -- bed om billede af typeskiltet, så bogstavet kan verificeres "
        "på maskinen i stedet for i teksten"
    ),
    "mærke+industrikategori": (
        "kendt sikkerhedsstøvsuger-mærke nævnt sammen med en industri-/"
        "byggestøvsuger-kategori, men HVERKEN modelnummer eller klassebogstav i "
        "teksten -- svageste kandidat-niveau, bed om typeskilt før alt andet"
    ),
}


def _kandidat_signal(listing: dict, config: dict) -> tuple[str | None, str | None]:
    """Returnerer (signalnavn, mangler_info-note) for en annonce UDEN bekræftet
    støvklasse -- se den lange kommentar ovenfor for de målte tal bag hvert
    trin. (None, None) betyder "ingen kandidat-evidens overhovedet", altså
    afvisning."""
    if listing.get("sikkerhedssuger_vokabular"):
        return "sikkerhedssuger-vokabular", _KANDIDAT_NOTER["sikkerhedssuger-vokabular"]
    if listing.get("klassebogstav_signal"):
        return "klassebogstav", _KANDIDAT_NOTER["klassebogstav"]
    if listing.get("known_brand_mentioned"):
        # Uændret gammel opførsel -- noten sættes af classify() selv længere
        # nede (den formulering brugeren allerede kender).
        return "mærke+modelnummer", None
    if listing.get("maerke_naevnt") and listing.get("industri_kategori"):
        floor = config.get(
            "minimumspris_svagt_signal_dkk", config.get("filter_replacement_estimate_dkk", 800)
        )
        price = listing.get("landed_price_dkk")
        # En pris på None er typisk en auktion uden bud endnu (klaravik/
        # auktionshuset/retrade) -- den må ikke tolkes som "gratis, altså støj",
        # så prisbunden springes over og annoncen beholdes som kandidat.
        if price is not None and price < floor:
            return None, None
        return "mærke+industrikategori", _KANDIDAT_NOTER["mærke+industrikategori"]
    return None, None


def compute_score(listing: dict) -> tuple[int, list[str]]:
    """Returnerer (score, forklaringer) -- forklaringer er til
    classification_method/audit, ikke vist direkte til brugeren."""
    score = 0
    reasons: list[str] = []

    # RETTET 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A): tidligere gav
    # asbestos_approved=True OG et rent tekst-udsagn ("asbestgodkendt", "TRGS
    # 519") det SAMME +3. Version 3 viser hvorfor det er forkert: fabrikantens
    # egen certificerings-sætning er SERIETEKST og står også på maskiner der
    # ikke må køre asbest (ATTIX 33-2M PC), så en sælger der afskriver
    # produktsiden kan skrive "asbestgodkendt" om en M-maskine i god tro.
    # Tre niveauer nu, og kun ÉT udløses (elif), så intet tælles dobbelt:
    #   1. model-niveau (models.py har bevis for netop denne model)  -> +3
    #   2. SKU-specifik mærkning i annonceteksten (ASBES/BG BAU/varenr.) -> +3
    #   3. sælgerens egen, ukvalificerede påstand                     -> +1
    if listing.get("asbestos_approved") is True:
        score += 3
        reasons.append("+3 asbestgodkendelse bekræftet på modelniveau")
    elif listing.get("asbest_sku_maerkning"):
        score += 3
        reasons.append("+3 SKU-specifik asbestmærkning i annoncetekst (ASBES/BG BAU/varenr.)")
    elif listing.get("asbest_godkendt_i_tekst"):
        score += 1
        reasons.append(
            "+1 sælger hævder asbestgodkendelse (kun annoncetekst -- kan være "
            "afskrevet serietekst, jf. stovsuger-modeloversigt2.md afsnit 7A)"
        )
    if listing.get("filterrensning") == "automatisk":
        score += 3
        reasons.append("+3 automatisk/semiautomatisk filterrensning")
    if listing.get("flowsensor") is True:
        score += 2
        reasons.append("+2 flowsensor")
    if listing.get("stikdaase") is True:
        score += 2
        reasons.append("+2 stikdåse m/autostart")
    if listing.get("antistatisk_slange"):
        score += 2
        reasons.append("+2 antistatisk slange")
    if listing.get("nyt_filter"):
        score += 2
        reasons.append("+2 nyt/nyligt skiftet filter")
    if listing.get("ubrugte_poser"):
        score += 1
        reasons.append("+1 ubrugte sikkerhedsfilterposer")
    container_l = listing.get("container_l")
    if container_l is not None and 25 <= container_l <= 50:
        score += 1
        reasons.append("+1 beholder 25-50 l")
    if listing.get("condition_red_flag"):
        score -= 3
        reasons.append("-3 tegn på slidt filter/revnet pakning")
    if listing.get("asbest_kort_i_brug"):
        score -= 3
        reasons.append("-3 sælger oplyser asbest-brug")
    if listing.get("brand") == "Hilti" and listing.get("asbestos_approved") is False:
        score -= 5
        reasons.append("-5 Hilti VC-serie (asbest fraskrevet af producenten)")

    return score, reasons


def classify(listing: dict, config: dict) -> dict:
    """Kernefunktion: tager et normaliseret listing-dict (fra normalize.py)
    + config.yaml's prisloft/scoring-sektion, returnerer et dict med
    score, vurdering, mangler_info, spoergsmaal_til_saelger,
    classification_method (til audit/frontend).

    Bruger landed_price_dkk (allerede inkl. evt. told/moms/fragt for
    ikke-EU-sælgere, se normalize.py) + et fast filterelement-estimat, per
    spec: "inkl. evt. transport" og "regn 700-900 kr. oveni".
    """
    mangler_info: list[str] = []
    price_cfg = config.get("prislofter", {})
    filter_estimate = config.get("filter_replacement_estimate_dkk", 800)

    hard_reject = listing.get("hard_reject", False)
    dust_class = listing.get("dust_class")
    weak_evidence_only = listing.get("weak_evidence_only", False)
    completeness_negative = listing.get("completeness_negative", False)
    battery = listing.get("battery", False)
    klasse_kilde = listing.get("klasse_kilde")

    price_dkk = listing.get("landed_price_dkk")
    # R8 (Opus 5-gennemgang, 2026-09-20): filterestimatet lægges KUN oveni
    # for en reelt BRUGT maskine (spec: "på enhver BRUGT maskine") -- en
    # eksplicit "fabriksny"/"ubrugt"-annonce (typisk forhandlersalg) skal
    # ikke straffes med et estimat der ikke gælder for den.
    skip_filter_estimate = listing.get("nyt_filter") or listing.get("unused_machine")
    effective_price = None
    if price_dkk is not None:
        effective_price = price_dkk if skip_filter_estimate else price_dkk + filter_estimate

    score, reasons = compute_score(listing)

    # --- Hårde porte (kan aldrig blive "køb nu", ofte direkte "afvis") ---
    if hard_reject:
        return _result(
            "afvis",
            score,
            reasons,
            [f"model på blacklist ({listing.get('reject_reason')})"],
            method=f"hård afvisning: {listing.get('reject_reason')}",
        )

    # Kandidat-stigen gælder KUN annoncer uden bekræftet støvklasse -- er
    # klassen allerede kendt (modelmatch eller eksplicit klasse-udsagn), er
    # der ikke noget at rangordne, og stigens noter ville være direkte
    # misvisende ("intet modelnavn matcher models.py").
    kandidat_signal, kandidat_note = (
        _kandidat_signal(listing, config) if dust_class in (None, "ukendt") else (None, None)
    )
    if dust_class in (None, "ukendt") and kandidat_signal is None:
        if weak_evidence_only:
            return _result(
                "afvis",
                score,
                reasons,
                [
                    "kun filter-/markedsførings-termer (HEPA/professionel/industri) -- "
                    "ingen dokumentation for MASKINENS støvklasse, jf. spec"
                ],
                method="afvist: kun svag evidens (filter-marketing, ikke maskinklasse)",
            )
        # KRITISK FUND (bruger diskvalificerede 10 rigtige DBA-fund manuelt
        # 2026-09-19, primært generiske "Støvsuger"/"Lille støvsuger"-annoncer
        # fundet via det brede "sikkerhedsstøvsuger"-søgeord): en annonce med
        # ABSOLUT INTET signal -- intet mærke, ingen klasse-omtale, ikke engang
        # svag markedsførings-evidens -- er reelt STØJ fra en bred søgning, ikke
        # en kandidat der fortjener "se nærmere". Her er der ingenting
        # overhovedet at spørge sælger om ud over de faste standardspørgsmål,
        # hvilket i praksis ikke er brugbart.
        return _result(
            "afvis",
            score,
            reasons,
            ["intet mærke, model eller klasse-omtale -- sandsynligvis støj fra bred søgning"],
            method="afvist: intet identificerbart signal",
        )
    if kandidat_note:
        mangler_info.append(kandidat_note)

    if completeness_negative:
        return _result(
            "afvis",
            score,
            reasons,
            ["annoncetekst tyder på ukomplet maskine (løsdele/uden slange/kun beholder)"],
            method="afvist: sandsynligt ukomplet maskine",
        )

    # Nypris-loft (70%) -- kun håndhævet når vi rent faktisk kender en nypris,
    # og KUN for en reelt BRUGT maskine. To rettelser (2026-09-20):
    # (1) Tjekkes mod selve UDBUDSPRISEN (price_dkk), IKKE effective_price
    #     (som inkluderer filterestimatet) -- ellers kan en billig,
    #     lav-nypris-model (fx Metabo ASA 30 H PC, nypris 2.349 kr.) aldrig
    #     bestå selv til en fair brugt-pris, fordi det faste
    #     700-900 kr.-filterestimat alene er en stor andel af maskinens
    #     egen værdi. Reglen er en sanity-check på selve prisen sælger
    #     beder om, adskilt fra prisloft-kategoriens køb/god-handel-grænser
    #     (som filterestimatet stadig indgår i, se effective_price ovenfor).
    # (2) Springes helt over når "unused_machine" er sandt -- reglens
    #     forudsætning er "en BRUGT maskine bør koste meningsfuldt mindre
    #     end en ny" (afskrivning for slid), hvilket er en kategorifejl at
    #     anvende på en bekræftet fabriksny/ubrugt maskine. Fundet konkret:
    #     "Nilfisk AERO 26-2H PC NU KUN 2.995 KR, fabriksny" blev afvist på
    #     70%-reglen alene, selvom prisloft-kategoriens egne grænser (som
    #     rent faktisk er designet til at vurdere om PRISEN er god) ikke
    #     har indvendinger.
    price_new_low = listing.get("price_new_dkk_low")
    if price_dkk is not None and price_new_low and not listing.get("unused_machine"):
        if price_dkk > 0.7 * price_new_low:
            return _result(
                "afvis",
                score,
                reasons,
                [
                    f"udbudspris ({price_dkk:.0f} kr.) overstiger 70% af kendt nypris "
                    f"({price_new_low:.0f} kr.)"
                ],
                method="afvist: over 70%-af-nypris-loftet",
            )

    if dust_class in (None, "ukendt") and kandidat_signal == "mærke+modelnummer":
        mangler_info.append(
            "kendt sikkerhedsstøvsuger-mærke nævnt, men modelnummer matcher ingen kendt "
            "H/M-model -- bed sælger om billede af typeskiltet (kan være en model.py "
            "endnu ikke dækker)"
        )
    elif dust_class in (None, "ukendt") and not kandidat_note:
        mangler_info.append("støvklasse (H/M) kan ikke bekræftes ud fra annoncens tekst")
    elif klasse_kilde == "annoncetekst":
        mangler_info.append(
            "støvklasse kun oplyst i annoncetekst, ikke bekræftet via modelnavn/typeskilt"
        )
    if dust_class == "M" and listing.get("asbestos_approved") is not True:
        mangler_info.append("M-klasse: asbest er IKKE bekræftet udelukket for denne model")
    # Ny 2026-09-29 (stovsuger-modeloversigt2.md, afsnit 7A): den konkrete fælde
    # version 3 afdækker -- annoncen PÅSTÅR asbestgodkendelse, men models.py kan
    # ikke bekræfte det for netop den model, og der er ingen SKU-specifik
    # mærkning i teksten. Det er præcis det mønster der opstår når en sælger
    # (eller en forhandler) afskriver fabrikantens serietekst. Bevidst SNÆVER:
    # den udløses KUN når påstanden faktisk står i annoncen, så den ikke
    # oversvømmer enhver almindelig H-annonce med støj (og dermed i praksis
    # afskaffer "køb nu" for alle andre mærker end Nilfisk/Flex).
    if (
        listing.get("asbestos_approved") is not True
        and listing.get("asbest_godkendt_i_tekst")
        and not listing.get("asbest_sku_maerkning")
    ):
        mangler_info.append(
            "annoncen påstår asbestgodkendelse, men den kan ikke bekræftes for denne "
            "model -- fabrikanternes egen certificeringstekst er ofte SERIETEKST og "
            "står også på maskiner der ikke må køre asbest. Bed om varenummer/"
            "art.nr. på typeskiltet"
        )
    if battery:
        mangler_info.append(
            "batterimaskine -- spec: kun sekundært fund, kræver 230V/ledning som hovedregel"
        )
    if listing.get("filterrensning") == "ukendt":
        mangler_info.append("filterrensningsmetode (automatisk/manuel) ikke oplyst")
    if listing.get("flowsensor") == "ukendt":
        mangler_info.append("flowsensor/volumenstrømsalarm ikke oplyst")
    if price_dkk is None:
        mangler_info.append("pris ikke tilgængelig (formentlig auktion uden aktuelt bud)")

    # --- Priskategori + loft ---
    category = _price_category(dust_class, container_l=listing.get("container_l"))
    ceilings = price_cfg.get(category) if category else None
    if ceilings and effective_price is not None:
        if effective_price > ceilings["koeb_max"]:
            return _result(
                "afvis",
                score,
                reasons,
                mangler_info
                + [
                    f"pris ({effective_price:.0f} kr. inkl. filterestimat) over købsloftet "
                    f"for {category} ({ceilings['koeb_max']} kr.)"
                ],
                method=f"afvist: over prisloft ({category})",
            )
        is_god_handel = effective_price <= ceilings["god_handel_max"]
    else:
        is_god_handel = False
        if category is None:
            mangler_info.append(
                "ukendt beholderstørrelse -- kan ikke placere i et prisloft-interval"
            )

    # --- Køb nu kræver: kendt god pris + verificeret klasse (ikke kun tekst) +
    # ikke batteri + (for M) bekræftet asbest-udelukkelse + ingen manglende info
    # om selve klassen. ---
    can_be_koeb_nu = (
        is_god_handel
        and dust_class not in (None, "ukendt")
        and klasse_kilde == "modelnavn"
        and not battery
        and (dust_class != "M" or listing.get("asbestos_approved") is True)
    )

    if can_be_koeb_nu and not mangler_info:
        return _result(
            "køb nu", score, reasons, mangler_info, method="godkendt: alle hårde krav + god pris"
        )

    # Kandidat-trinnet navngives i classification_method (audit-feltet, samme
    # rolle som "hård afvisning: <mønster>") -- uden det kan brugeren ikke se
    # HVILKEN af de fire regler der lukkede en given annonce ind, og dermed
    # heller ikke afgøre om et enkelt trin skal strammes igen.
    method = "se nærmere: mangler verifikation eller pris over 'god handel'"
    if kandidat_signal is not None:
        method += f" (kandidat-signal: {kandidat_signal})"
    return _result("se nærmere", score, reasons, mangler_info, method=method)


def _result(
    vurdering: str, score: int, reasons: list[str], mangler_info: list[str], *, method: str
) -> dict:
    return {
        "vurdering": vurdering,
        "score": score,
        "score_reasons": reasons,
        "mangler_info": mangler_info,
        "classification_method": method,
        "spoergsmaal_til_saelger": list(SELLER_QUESTIONS) if vurdering == "se nærmere" else [],
    }
