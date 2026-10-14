import concurrent.futures
import copy
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from gabriel_gadget.backend import Backends, validate_origin
from gabriel_gadget.bridge import Bridge, make_server
from gabriel_gadget.device import Device
from gabriel_gadget.errors import GadgetError
from gabriel_gadget.packs import Catalog, read_json
from gabriel_gadget.store import Store


class BridgeInteraction(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.token = self.store.enroll("desk", Catalog().names())
        self.identity = self.store.authenticate(self.token)
        self.bridge = Bridge(self.store)
        self.server = make_server(self.bridge, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.device = Device(self.origin, self.token, allow_loopback_http=True)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.temp.cleanup()

    def test_boli_kai_chakri_shared_real_http_interaction_and_review(self):
        self.assertEqual(len(self.device.catalog()), 14)
        for persona, expected in (("boli", "adult_review_required"), ("kai", "approval_required"), ("chakri", "approval_required")):
            caps = self.device.capabilities(persona)
            self.assertFalse(caps["voice"])
            result = self.device.turn(persona, "shared-" + persona)
            self.assertEqual(result["status"], expected)
            receipt = self.device.review(result["operationId"], result["revision"], "approve")
            self.assertEqual(receipt["status"], "simulated_approval")
            self.assertEqual(receipt["externalEffects"], [])

    def test_remaining_eleven_domain_journeys_over_real_http(self):
        for name in Catalog().names():
            if name in ("boli", "kai", "chakri"):
                continue
            result = self.device.turn(name, "journey-" + name)
            self.assertEqual(result["persona"], name)
            self.assertEqual(result["externalEffects"], [])

    def test_restart_retains_receipt_and_same_operation_returns_identical_result(self):
        request = {"persona": "kai", "backend": "fixture", "operationId": "restart-kai"}
        result = self.bridge.turn(self.identity, request)
        restored = Bridge(Store(self.temp.name))
        self.assertEqual(restored.turn(self.identity, request), result)
        request["text"] = "different"
        with self.assertRaisesRegex(GadgetError, "different request"):
            restored.turn(self.identity, request)

    def test_read_only_receipt_recovery_returns_completed_result(self):
        result = self.device.turn("boli", "receipt-recovery")
        receipt = self.device.receipt("receipt-recovery")
        self.assertEqual(receipt["status"], "done")
        self.assertEqual(receipt["result"], result)
        with self.assertRaises(GadgetError):
            self.device.receipt("unknown-operation")

    def test_two_devices_cannot_read_or_review_each_others_result(self):
        result = self.device.turn("kai", "private-kai")
        second = self.store.authenticate(self.store.enroll("other", ["boli"]))
        with self.assertRaisesRegex(GadgetError, "not enrolled"):
            self.bridge.turn(second, {"persona": "kai", "operationId": "new-other-op"})
        with self.assertRaisesRegex(GadgetError, "not found"):
            self.store.review_fixture("other", "private-kai", result["revision"], "approve")

    def test_review_of_changed_proposal_revision_is_rejected(self):
        result = self.device.turn("paya", "review-paya")
        with self.assertRaisesRegex(GadgetError, "current complete proposal"):
            self.device.review("review-paya", "old-revision", "approve")
        self.device.review("review-paya", result["revision"], "decline")
        with self.assertRaisesRegex(GadgetError, "different decision"):
            self.device.review("review-paya", result["revision"], "approve")

    def test_revocation_and_rotation_take_effect(self):
        new = self.store.rotate("desk")
        with self.assertRaises(GadgetError):
            self.device.catalog()
        self.assertEqual(self.store.authenticate(new)["id"], "desk")
        self.store.revoke("desk")
        with self.assertRaises(GadgetError):
            self.store.authenticate(new)

    def test_concurrent_replays_reserve_only_one_operation(self):
        def reserve(_):
            try:
                return self.store.reserve("desk", "concurrent-turn", "digest")
            except GadgetError:
                return "held"
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(12)))
        self.assertEqual(results.count(None), 1)
        self.assertEqual(results.count("held"), 11)

    def test_uncertain_turn_is_never_automatically_replayed(self):
        self.store.reserve("desk", "uncertain-turn", "digest")
        self.store.fail("desk", "uncertain-turn")
        with self.assertRaisesRegex(GadgetError, "uncertain"):
            self.store.reserve("desk", "uncertain-turn", "digest")

    def test_credentials_never_leak_into_catalog_or_status(self):
        self.assertNotIn(self.token, json.dumps(self.device.catalog()))
        with self.store.connect() as db:
            self.assertNotIn(self.token, json.dumps([dict(x) for x in db.execute("SELECT * FROM devices")]))
        self.assertEqual(Path(self.temp.name, "state.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_invalid_json_and_unauthed_request_fail(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.origin + "/v1/catalog")
        self.assertEqual(error.exception.code, 401)
        req = urllib.request.Request(self.origin + "/v1/turns", data=b'{"facts":NaN}',
                                     headers={"Authorization": "Bearer " + self.token})
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(req)
        self.assertEqual(error.exception.code, 400)

    def test_fixture_voice_and_undeclared_command_fail_closed(self):
        with self.assertRaisesRegex(GadgetError, "speech recognition"):
            self.device.turn("boli", "voice-fixture", audioBase64="UklGRg==")
        with self.assertRaisesRegex(GadgetError, "not declared"):
            self.device.turn("boli", "undeclared-cmd", command="transfer-money")

    def test_lan_server_requires_tls_and_local_backend_cannot_be_public(self):
        with self.assertRaisesRegex(GadgetError, "requires --cert"):
            make_server(self.bridge, host="0.0.0.0", port=0)
        with self.assertRaisesRegex(GadgetError, "HTTPS"):
            validate_origin("http://192.168.1.10", "local")
        with self.assertRaises(GadgetError):
            validate_origin("https://user:secret@example.com", "cloud")


if __name__ == "__main__":
    unittest.main()
