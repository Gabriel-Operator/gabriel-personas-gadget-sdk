import copy
import json
import tempfile
import unittest
from pathlib import Path

from gabriel_gadget.cli import scaffold, validate
from gabriel_gadget.errors import GadgetError
from gabriel_gadget.fixtures import evaluate
from gabriel_gadget.packs import Catalog, read_json, validate_pack


class DomainExamples(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()

    def facts(self, name):
        return read_json(self.catalog.path(name) / "fixture.json")

    def run_example(self, name, facts=None):
        return evaluate(self.catalog.get(name), facts if facts is not None else self.facts(name))

    def test_all_fourteen_reproducible_packages_and_scenario_checks(self):
        self.assertEqual(set(self.catalog.names()), {"lane", "sherma", "nest", "juno", "lina", "kai",
            "emil", "nora", "archer", "cole", "boli", "chakri", "paya", "mirav"})
        self.assertEqual(validate(self.catalog)["packages"], 14)
        for name in self.catalog.names():
            self.assertEqual(self.run_example(name)["externalEffects"], [])

    def test_boli_requires_age_boundary_and_adult_evidence_review(self):
        result = self.run_example("boli")
        self.assertEqual(result["observations"], ["The lamp is off with an open switch", "The lamp turns on with a closed switch"])
        self.assertFalse(result["masteryAwarded"])
        for age in (8, 19):
            facts = self.facts("boli"); facts["learnerAge"] = age
            with self.assertRaisesRegex(GadgetError, "9–18"):
                self.run_example("boli", facts)

    def test_kai_orders_only_the_gap_and_uses_cited_integer_prices(self):
        result = self.run_example("kai")
        self.assertEqual([(x["item"], x["quantity"], x["lineTotalCents"]) for x in result["cart"]],
                         [("tomato", 1, 40), ("pasta", 0.5, 90), ("spinach", 2, 150)])
        self.assertEqual(result["totalCents"], 280)
        facts = self.facts("kai"); facts["inventory"] = {"tomato": 3, "pasta": 1, "spinach": 2}
        self.assertEqual(self.run_example("kai", facts)["cart"], [])
        facts = self.facts("kai"); del facts["offers"]["spinach"]
        with self.assertRaisesRegex(GadgetError, "Missing cited price"):
            self.run_example("kai", facts)

    def test_kai_changed_price_changes_review_revision(self):
        facts = self.facts("kai"); original = self.run_example("kai", facts)
        facts["offers"]["tomato"]["unitPrice"] = 0.8
        changed = self.run_example("kai", facts)
        self.assertNotEqual(original["revision"], changed["revision"])
        self.assertEqual(changed["totalCents"], 320)

    def test_chakri_rate_card_area_and_weight_boundaries(self):
        result = self.run_example("chakri")
        self.assertEqual(result["estimatedTotalCents"], 220)
        self.assertTrue(result["acceptedWeightRequired"])
        self.assertFalse(result["paymentPerformed"])
        facts = self.facts("chakri"); facts["area"] = "Outside District"
        with self.assertRaisesRegex(GadgetError, "does not serve"):
            self.run_example("chakri", facts)
        facts = self.facts("chakri"); facts["materials"][0]["material"] = "unknown"
        with self.assertRaisesRegex(GadgetError, "absent from the rate card"):
            self.run_example("chakri", facts)

    def test_lane_evidence_filters_irrelevant_and_unverified_candidates(self):
        facts = self.facts("lane")
        facts["companies"].append({"id": "unverified", "name": "Unknown", "sectors": ["energy"]})
        result = self.run_example("lane", facts)
        self.assertEqual([x["id"] for x in result["candidates"]], ["company-a"])

    def test_sherma_missing_field_never_submits(self):
        result = self.run_example("sherma")
        self.assertEqual(result["missingFields"], ["address"])
        self.assertFalse(result["submitted"])

    def test_nest_returns_one_candidate_and_no_address(self):
        result = self.run_example("nest")
        self.assertEqual(result["candidate"]["id"], "home-a")
        self.assertNotIn("address", result["candidate"])
        self.assertNotIn("Synthetic private address", json.dumps(result))

    def test_juno_never_discloses_private_identity(self):
        result = self.run_example("juno")
        self.assertEqual(result["sharedValues"], ["kindness"])
        self.assertNotIn("Private synthetic person", json.dumps(result))

    def test_lina_does_not_invent_unevidenced_skills_or_send(self):
        result = self.run_example("lina")
        self.assertEqual(result["evidence"], ["Python", "SQL"])
        self.assertEqual(result["unverifiedSkills"], ["Kafka"])
        self.assertFalse(result["outreachSent"])

    def test_emil_preserves_declarant_and_reports_missing_document(self):
        result = self.run_example("emil")
        self.assertEqual(result["missingDocuments"], ["origin-certificate"])
        self.assertFalse(result["portalTwin"]["ready"])
        self.assertFalse(result["filed"])

    def test_nora_flags_policy_exception_without_payment(self):
        result = self.run_example("nora")
        self.assertEqual(result["exceptions"], ["Amount exceeds policy review limit"])
        self.assertFalse(result["paymentPerformed"])

    def test_archer_requires_source_and_never_fakes_generated_images(self):
        result = self.run_example("archer")
        self.assertEqual(result["imageGeneration"], "requires connected media provider")
        facts = self.facts("archer"); del facts["brand"]["source"]
        with self.assertRaisesRegex(GadgetError, "restaurant source"):
            self.run_example("archer", facts)

    def test_cole_plans_from_existing_closet(self):
        result = self.run_example("cole")
        self.assertEqual(result["ownedItems"], ["Owned navy jacket", "Owned cream shirt"])
        self.assertFalse(result["purchaseSuggested"])

    def test_paya_expiry_stock_budget_and_exact_plan_revision(self):
        original = self.run_example("paya")
        for key, value in (("stock", 0), ("totalCents", 20000), ("expiresAt", "2026-10-14T09:00:00Z")):
            facts = self.facts("paya"); facts["offer"][key] = value
            result = self.run_example("paya", facts)
            self.assertEqual(result["status"], "offer_unavailable")
            self.assertNotEqual(original["revision"], result["revision"])

    def test_mirav_geofence_consent_and_location_privacy(self):
        result = self.run_example("mirav")
        self.assertEqual(result["eligibleFamilies"], ["family-a"])
        self.assertFalse(result["exactLocationsDisclosed"])
        facts = self.facts("mirav"); facts["geofence"]["enabled"] = False
        with self.assertRaisesRegex(GadgetError, "explicitly enabled"):
            self.run_example("mirav", facts)

    def test_custom_persona_scaffold_runs_without_private_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gardener"
            scaffold(path, "gardener", "Fern", "garden planning", "Ask before buying or spraying anything.")
            manifest = validate_pack(path)
            result = evaluate(manifest, read_json(path / "fixture.json"))
            self.assertEqual(result["persona"], "gardener")
            self.assertFalse(result["actionPerformed"])
            with self.assertRaises(GadgetError):
                scaffold(path, "gardener", "Fern", "garden", "Review.")


if __name__ == "__main__":
    unittest.main()
