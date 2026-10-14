import base64
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from gabriel_gadget.backend import Backends, GabrielPersona, validate_origin
from gabriel_gadget.bridge import Bridge
from gabriel_gadget.errors import BackendError, GadgetError
from gabriel_gadget.store import Store


class ApiContract(unittest.TestCase):
    """Real HTTP sockets with a synthetic Persona API; not live-provider evidence."""
    def setUp(self):
        self.calls = []
        self.api_error = None
        self.audio_redirect = None
        self.api_caps = ["chat", "commands", "stt", "tts"]
        self.model = "gabriel/published-boli"
        owner = self

        class API(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def send(self, value, mime="application/json"):
                raw = json.dumps(value).encode() if mime == "application/json" else value
                self.send_response(200); self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

            def do_GET(self):
                owner.calls.append(("GET", self.path, self.headers.get("Authorization")))
                if self.path == "/api/v1/models":
                    self.send({"data": [{"id": owner.model, "name": "Boli", "capabilities": owner.api_caps}]})
                elif self.path == "/api/v1/commands":
                    self.send({"data": [{"trigger": "learn-course"}]})
                else:
                    self.send_error(404)

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"]))
                owner.calls.append(("POST", self.path, data))
                if owner.api_error:
                    self.send_error(owner.api_error); return
                if self.path == "/api/v1/audio/transcriptions":
                    if b'name="file"' not in data or b"RIFF" not in data:
                        self.send_error(400); return
                    self.send({"text": "Explain the circuit."})
                elif self.path == "/api/v1/audio/speech":
                    if owner.audio_redirect:
                        self.send_response(302); self.send_header("Location", owner.audio_redirect)
                        self.send_header("Content-Length", "0"); self.end_headers()
                    else:
                        self.send(b"synthetic-mp3-bytes", "audio/mpeg")
                elif self.path == "/api/v1/commands/learn-course":
                    self.send({"object": "command_result", "status": "requires_input", "data": {"review": "adult"}})
                elif self.path == "/api/v1/chat/completions":
                    body = json.loads(data)
                    if body.get("stream"):
                        raw = ("data: " + json.dumps({"choices": [{"delta": {"content": "First "}}]}) + "\r\n\r\n" +
                               "data: " + json.dumps({"choices": [{"delta": {"content": "reply"}}], "gabriel": {"session_id": "stream-session"}}) +
                               "\n\ndata: [DONE]\n\n").encode()
                        self.send(raw, "text/event-stream")
                    else:
                        self.send({"choices": [{"message": {"content": "Synthetic Boli reply"}}],
                                   "gabriel": {"session_id": body.get("metadata", {}).get("session_id", "session-boli"), "events": []}})
                else:
                    self.send_error(404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), API)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.device = self.store.authenticate(self.store.enroll("device-a", ["boli"]))
        self.config = {"profiles": {mode: {"origin": self.origin, "allowLoopbackHttp": True,
            "bindings": {"boli": {"tokenEnv": "GADGET_TEST_TOKEN", "personaId": "published-boli"}}}
            for mode in ("cloud", "local")}}
        self.env = patch.dict(os.environ, {"GADGET_TEST_TOKEN": "gabi_contract_placeholder"}); self.env.start()
        self.bridge = Bridge(self.store, backends=Backends(self.config))

    def tearDown(self):
        self.env.stop(); self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def client(self):
        return GabrielPersona(self.origin, "gabi_contract_placeholder", "published-boli", allow_loopback_http=True)

    def test_cloud_and_local_routes_use_same_api_and_isolated_sessions(self):
        for mode in ("cloud", "local"):
            result = self.bridge.turn(self.device, {"persona": "boli", "backend": mode,
                                                   "operationId": "first-" + mode, "text": "Explain the circuit."})
            self.assertEqual(result["mode"], mode)
            self.assertEqual(result["sessionId"], "session-boli")
            self.bridge.turn(self.device, {"persona": "boli", "backend": mode,
                                          "operationId": "second-" + mode, "text": "What changed?"})
        posts = [json.loads(x[2]) for x in self.calls if x[0] == "POST" and x[1].endswith("chat/completions")]
        self.assertEqual(posts[1]["metadata"]["session_id"], "session-boli")
        self.assertNotIn("metadata", posts[2])
        self.assertEqual(posts[0]["user"], "gadget:device-a")

    def test_completed_live_receipt_can_be_read_when_backend_is_unavailable(self):
        body = {"persona": "boli", "backend": "cloud", "operationId": "completed-turn", "text": "Hello"}
        result = self.bridge.turn(self.device, body); before = len(self.calls)
        restored = Bridge(Store(self.temp.name))  # no configured backend
        self.assertEqual(restored.turn(self.device, body), result)
        self.assertEqual(len(self.calls), before)

    def test_sse_handles_crlf_deltas_and_completion(self):
        chunks = list(self.client().chat_stream("Hello", "test-user"))
        self.assertEqual("".join(x["choices"][0]["delta"]["content"] for x in chunks), "First reply")
        self.assertEqual(chunks[-1]["gabriel"]["session_id"], "stream-session")

    def test_batch_voice_transcribes_chats_and_returns_audio(self):
        result = self.bridge.turn(self.device, {"persona": "boli", "backend": "cloud", "operationId": "voice-turn",
            "audioBase64": base64.b64encode(b"RIFFsynthetic-wav").decode(), "audioMime": "audio/wav", "speak": True})
        self.assertEqual(base64.b64decode(result["audio"]["base64"]), b"synthetic-mp3-bytes")
        paths = [x[1] for x in self.calls if x[0] == "POST"]
        self.assertEqual(paths, ["/api/v1/audio/transcriptions", "/api/v1/chat/completions", "/api/v1/audio/speech"])

    def test_disabled_speech_fails_before_any_post(self):
        self.api_caps = ["chat"]
        with self.assertRaisesRegex(GadgetError, "lacks a requested"):
            self.bridge.turn(self.device, {"persona": "boli", "backend": "cloud", "operationId": "disabled-voice", "text": "Hello", "speak": True})
        self.assertFalse(any(x[0] == "POST" for x in self.calls))

    def test_wrong_persona_binding_fails_before_any_post(self):
        self.model = "gabriel/some-other-persona"
        with self.assertRaisesRegex(GadgetError, "different published persona"):
            self.bridge.turn(self.device, {"persona": "boli", "backend": "cloud", "operationId": "wrong-binding", "text": "Hello"})
        self.assertFalse(any(x[0] == "POST" for x in self.calls))

    def test_command_discovery_uses_data_and_preserves_session(self):
        self.assertEqual(self.client().commands()[0]["trigger"], "learn-course")
        self.store.save_session("device-a", "boli", "cloud", "existing-session")
        result = self.bridge.turn(self.device, {"persona": "boli", "backend": "cloud", "operationId": "command-turn",
            "command": "learn-course", "text": "A circuit lesson"})
        self.assertEqual(result["result"]["status"], "requires_input")
        payload = json.loads([x[2] for x in self.calls if x[0] == "POST"][-1])
        self.assertEqual(payload["metadata"]["session_id"], "existing-session")

    def test_rate_limit_never_replays_post_and_uncertain_receipt_blocks_retry(self):
        self.api_error = 429
        body = {"persona": "boli", "backend": "cloud", "operationId": "limited-turn", "text": "Hello"}
        with self.assertRaisesRegex(BackendError, "rate limited"):
            self.bridge.turn(self.device, body)
        with self.assertRaisesRegex(GadgetError, "uncertain"):
            self.bridge.turn(self.device, body)
        self.assertEqual(len([x for x in self.calls if x[0] == "POST"]), 1)

    def test_device_cannot_approve_a_live_effect(self):
        result = self.bridge.turn(self.device, {"persona": "boli", "backend": "cloud", "operationId": "live-review", "text": "Hello"})
        with self.assertRaisesRegex(GadgetError, "authenticated Persona app"):
            self.store.review_fixture("device-a", "live-review", result.get("revision"), "approve")

    def test_local_speech_cannot_download_a_cloud_redirect(self):
        self.audio_redirect = "https://8.8.8.8/private-audio.wav"
        result = self.bridge.turn(self.device, {"persona": "boli", "backend": "local", "operationId": "local-speech-redirect", "text": "Hello", "speak": True})
        self.assertEqual(result["text"], "Synthetic Boli reply")
        self.assertIn("speechError", result)
        self.assertNotIn("audio", result)


if __name__ == "__main__":
    unittest.main()
