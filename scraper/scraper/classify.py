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
]

_PRICE_CATEGORY_COMPACT_H = "kompakt_h"
_PRICE_CATEGORY_LARGE_H = "stor_h"
_PRICE_CATEGORY_M = "m_klasse"


def _price_category(dust_class: str | None, container_l: float | None) -> str | None:
    if dust_class == "M":
        return _PRICE_CATEGORY_M
    if dust_class == "H" and container_l is not None:
        if 25 <= container_l <= 35:
            return _PRICE_CATEGORY_COMPACT_H
        if 40 <= container_l <= 75:
            return _PRICE_CATEGORY_LARGE_H
    return None


def compute_score(listing: dict) -> tuple[int, list[str]]:
    """Returnerer (score, forklaringer) -- forklaringer er til
    classification_method/audit, ikke vist direkte til brugeren."""
    score = 0
    reasons: list[str] = []

    if listing.get("asbestos_approved") is True or listing.get("asbest_godkendt_i_tekst"):
        score += 3
        reasons.append("+3 asbestgodkendelse")
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

    known_brand_mentioned = listing.get("known_brand_mentioned", False)
    if dust_class in (None, "ukendt") and weak_evidence_only and not known_brand_mentioned:
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
    # en kandidat der fortjener "se nærmere". Bredere end weak_evidence_only-
    # tjekket ovenfor (som kræver eksplicit HEPA/professionel-tekst): her er
    # der ingenting overhovedet at spørge sælger om ud over de faste 6
    # standardspørgsmål, hvilket i praksis ikke er brugbart.
    if dust_class in (None, "ukendt") and not known_brand_mentioned and not weak_evidence_only:
        return _result(
            "afvis",
            score,
            reasons,
            ["intet mærke, model eller klasse-omtale -- sandsynligvis støj fra bred søgning"],
            method="afvist: intet identificerbart signal",
        )

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

    if dust_class in (None, "ukendt") and known_brand_mentioned:
        mangler_info.append(
            "kendt sikkerhedsstøvsuger-mærke nævnt, men modelnummer matcher ingen kendt "
            "H/M-model -- bed sælger om billede af typeskiltet (kan være en model.py "
            "endnu ikke dækker)"
        )
    elif dust_class in (None, "ukendt"):
        mangler_info.append("støvklasse (H/M) kan ikke bekræftes ud fra annoncens tekst")
    elif klasse_kilde == "annoncetekst":
        mangler_info.append(
            "støvklasse kun oplyst i annoncetekst, ikke bekræftet via modelnavn/typeskilt"
        )
    if dust_class == "M" and listing.get("asbestos_approved") is not True:
        mangler_info.append("M-klasse: asbest er IKKE bekræftet udelukket for denne model")
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

    return _result(
        "se nærmere",
        score,
        reasons,
        mangler_info,
        method="se nærmere: mangler verifikation eller pris over 'god handel'",
    )


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
