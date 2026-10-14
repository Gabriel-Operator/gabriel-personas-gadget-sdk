"""Deterministic domain work with synthetic data; never makes external effects."""
from decimal import Decimal, ROUND_HALF_UP

from .errors import GadgetError
from .packs import fingerprint


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def evaluate(manifest, facts):
    name = manifest["fixtureEngine"]
    if not isinstance(facts, dict):
        raise GadgetError("invalid_input", "Fixture facts must be an object.")
    try:
        result = ENGINES[name](facts)
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        raise GadgetError("invalid_input", "Required domain facts are missing or invalid.") from exc
    result.update({"mode": "fixture", "persona": manifest["id"],
                   "externalEffects": [], "boundary": manifest["boundary"]})
    result["revision"] = fingerprint(result)
    return result


def boli(f):
    age = f["learnerAge"]
    if not isinstance(age, int) or not 9 <= age <= 18:
        raise GadgetError("age_out_of_scope", "Boli examples are for learners aged 9–18.")
    lesson = f["lesson"]
    return {"status": "adult_review_required", "title": lesson["title"],
            "question": lesson["question"], "observations": f["observations"],
            "nextStep": "Explain the pattern in your own words, then ask your adult to review.",
            "masteryAwarded": False, "source": lesson["source"]}


def kai(f):
    inventory = f["inventory"]
    if any(not isinstance(q, (int, float)) or q < 0 for q in inventory.values()):
        raise ValueError("Negative inventory")
    lines = []
    for item, needed in f["recipe"]["ingredients"].items():
        gap = max(0, needed - inventory.get(item, 0))
        if gap:
            offer = f["offers"].get(item)
            if not offer or not offer.get("source") or offer["unitPrice"] < 0:
                raise GadgetError("price_unavailable", "Missing cited price for " + item)
            lines.append({"item": item, "quantity": gap, "unitPriceCents": cents(offer["unitPrice"]),
                          "lineTotalCents": cents(Decimal(str(gap)) * Decimal(str(offer["unitPrice"]))),
                          "source": offer["source"]})
    return {"status": "approval_required", "meal": f["recipe"]["name"], "cart": lines,
            "totalCents": sum(x["lineTotalCents"] for x in lines), "currency": f["currency"],
            "checkoutPerformed": False, "signal": "Recipe inventory gap"}


def chakri(f):
    lines = []
    for item in f["materials"]:
        if item["estimatedKg"] < 0:
            raise ValueError("Negative weight")
        rate = f["rateCard"]["rates"].get(item["material"])
        if rate is None or rate < 0:
            raise GadgetError("rate_unavailable", "Material is absent from the rate card.")
        lines.append({"material": item["material"], "estimatedKg": item["estimatedKg"],
                      "estimatedValueCents": cents(Decimal(str(item["estimatedKg"])) * Decimal(str(rate)))})
    if f["area"] not in f["rateCard"]["serviceAreas"]:
        raise GadgetError("outside_service_area", "Collector does not serve this area.")
    return {"status": "approval_required", "quote": lines, "currency": f["rateCard"]["currency"],
            "estimatedTotalCents": sum(x["estimatedValueCents"] for x in lines),
            "source": f["rateCard"]["source"], "paymentPerformed": False,
            "acceptedWeightRequired": True, "pickup": f["requestedSlot"]}


def lane(f):
    thesis = set(f["thesis"])
    candidates = [c for c in f["companies"] if c.get("source") and thesis.intersection(c["sectors"])]
    candidates.sort(key=lambda c: (-len(thesis.intersection(c["sectors"])), c["id"]))
    return {"status": "introduction_review_required", "candidates": [
        {"id": c["id"], "name": c["name"], "source": c["source"],
         "reason": sorted(thesis.intersection(c["sectors"]))} for c in candidates], "introductionSent": False}


def sherma(f):
    fields = f["form"]["requiredFields"]
    missing = [k for k in fields if not f["records"].get(k)]
    return {"status": "needs_input" if missing else "review_required", "missingFields": missing,
            "formTwin": {k: f["records"].get(k) for k in fields}, "submitted": False,
            "source": f["form"]["source"]}


def nest(f):
    homes = [h for h in f["homes"] if h["price"] <= f["buyer"]["budget"] and
             set(f["buyer"]["mustHaves"]).issubset(h["features"])]
    homes.sort(key=lambda h: h["id"])
    c = homes[0] if homes else None
    return {"status": "mutual_consent_required" if c else "no_match", "candidate":
            {"id": c["id"], "features": c["features"], "price": c["price"]} if c else None,
            "privateDetailsDisclosed": False, "introductionSent": False}


def juno(f):
    shared = sorted(set(f["person"]["values"]).intersection(f["candidate"]["values"]))
    return {"status": "mutual_consent_required" if shared else "no_match", "sharedValues": shared,
            "candidateId": f["candidate"]["id"] if shared else None, "identityDisclosed": False,
            "introductionSent": False}


def lina(f):
    evidence = sorted(set(f["role"]["skills"]).intersection(f["candidate"]["evidencedSkills"]))
    return {"status": "recruiter_review_required", "evidence": evidence, "source": f["candidate"]["source"],
            "unverifiedSkills": sorted(set(f["role"]["skills"]) - set(evidence)),
            "outreachDraft": "Discuss demonstrated " + ", ".join(evidence) + " for " + f["role"]["title"],
            "outreachSent": False}


def emil(f):
    missing = sorted(set(f["requiredDocuments"]) - set(f["shipment"]["documents"]))
    return {"status": "declarant_review_required", "missingDocuments": missing,
            "portalTwin": {"shipmentReference": f["shipment"]["reference"], "ready": not missing},
            "declarant": "Licensed human declarant", "filed": False}


def nora(f):
    allowed = f["request"]["amountCents"] <= f["policy"]["reviewLimitCents"]
    return {"status": "banker_review_required", "withinPolicyLimit": allowed,
            "exceptions": [] if allowed else ["Amount exceeds policy review limit"],
            "policySource": f["policy"]["source"], "paymentPerformed": False}


def archer(f):
    if not f["brand"].get("source"):
        raise GadgetError("brand_evidence_required", "A restaurant source is required.")
    return {"status": "brand_review_required", "brief": {"venue": f["brand"]["name"],
            "event": f["event"], "observedColours": f["brand"]["colours"], "source": f["brand"]["source"]},
            "imageGeneration": "requires connected media provider", "published": False}


def cole(f):
    items = [x["name"] for x in f["closet"] if f["occasion"] in x["occasions"]]
    return {"status": "wardrobe_plan", "occasion": f["occasion"], "ownedItems": items,
            "purchaseSuggested": False, "virtualTryOn": "requires installed or connected image model"}


def paya(f):
    offer = f["offer"]
    valid = offer["stock"] > 0 and offer["totalCents"] <= f["budgetCents"] and f["now"] < offer["expiresAt"]
    return {"status": "approval_required" if valid else "offer_unavailable", "seller": offer["seller"],
            "totalCents": offer["totalCents"], "expiresAt": offer["expiresAt"], "currency": offer["currency"],
            "source": offer["source"], "checkoutPerformed": False, "changedPlanRequiresNewApproval": True}


def mirav(f):
    if not f["geofence"]["enabled"]:
        raise GadgetError("location_consent_required", "Location scope must be explicitly enabled.")
    eligible = [p["id"] for p in f["families"] if p["distanceMeters"] <= f["geofence"]["radiusMeters"]
                and f["activity"] in p["interests"]]
    return {"status": "mutual_consent_required", "activity": f["activity"], "eligibleFamilies": eligible,
            "exactLocationsDisclosed": False, "introductionSent": False, "programmeStatus": "draft"}


def custom(f):
    return {"status": "review_required", "summary": f["task"], "source": f["source"], "actionPerformed": False}


ENGINES = {k: v for k, v in locals().copy().items() if k in {
    "lane", "sherma", "nest", "juno", "lina", "kai", "emil", "nora", "archer", "cole",
    "boli", "chakri", "paya", "mirav", "custom"}}
