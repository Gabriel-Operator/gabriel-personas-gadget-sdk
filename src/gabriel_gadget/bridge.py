"""Authenticated gadget HTTP interface, backed by hosted or local Persona APIs."""
import base64
import json
import re
import ssl
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .backend import Backends
from .errors import GadgetError
from .fixtures import evaluate
from .packs import Catalog, fingerprint, read_json

MAX_BODY = 3 * 1024 * 1024
OPERATION = re.compile(r"^[A-Za-z0-9_-]{8,96}$")
PORTRAIT = re.compile(r"^/portraits/([a-z][a-z0-9-]{0,47})\.jpg$")


class Bridge:
    def __init__(self, store, catalog=None, backends=None):
        self.store = store
        self.catalog = catalog or Catalog()
        self.backends = backends or Backends()

    def persona(self, device, persona):
        if persona not in device["personas"]:
            raise GadgetError("persona_forbidden", "This device is not enrolled for this persona.", 403)
        return self.catalog.get(persona)

    def capabilities(self, device, persona, backend):
        m = self.persona(device, persona)
        if backend == "fixture":
            return {"persona": persona, "backend": backend, "capabilities": ["fixture", "text", "simulated_review"],
                    "commands": m["commands"], "voice": False, "externalEffects": False}
        client = self.backends.client(backend, persona)
        caps = client.capabilities()
        return {"persona": persona, "backend": backend, **caps,
                "voice": "stt" in caps["capabilities"],
                "review": "Protected actions must be reviewed in the authenticated Persona app."}

    def turn(self, device, body):
        if not isinstance(body, dict):
            raise GadgetError("invalid_request", "Turn must be a JSON object.")
        persona, mode, op = body.get("persona"), body.get("backend", "fixture"), body.get("operationId", "")
        m = self.persona(device, persona)
        if mode not in ("fixture", "cloud", "local") or not isinstance(op, str) or not OPERATION.fullmatch(op):
            raise GadgetError("invalid_request", "Choose a backend and a stable operation ID (8–96 portable characters).")
        text = body.get("text", "")
        if not isinstance(text, str) or len(text) > 16384:
            raise GadgetError("invalid_request", "Text must be a string of at most 16,384 characters.")
        trigger = body.get("command")
        if trigger is not None and trigger not in m["commands"]:
            raise GadgetError("command_forbidden", "Command is not declared by this persona package.", 403)
        if trigger is not None and body.get("audioBase64"):
            raise GadgetError("invalid_request", "Use text for explicit command invocation.")
        image = body.get("imageUrl")
        audio_format = body.get("audioFormat", "mp3")
        if audio_format not in ("mp3", "wav"):
            raise GadgetError("invalid_audio_format", "Choose mp3 or wav for reply audio.")
        if image is not None and (not isinstance(image, str) or len(image) > 4096 or
                                  urlsplit(image).scheme != "https" or not urlsplit(image).hostname or
                                  urlsplit(image).username):
            raise GadgetError("invalid_image", "Image input must be a bounded HTTPS URL without credentials.")
        audio = None
        if body.get("audioBase64"):
            if mode == "fixture":
                raise GadgetError("fixture_voice_unavailable", "Fixture demos do not perform speech recognition.")
            try:
                audio = base64.b64decode(body["audioBase64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise GadgetError("invalid_audio", "Audio must be base64 encoded.") from exc
            if not audio or len(audio) > 2 * 1024 * 1024 or body.get("audioMime", "audio/wav") not in (
                "audio/wav", "audio/mpeg", "audio/webm", "audio/ogg"
            ):
                raise GadgetError("invalid_audio", "Audio must be a supported format, at most 2 MiB.")
        digest = fingerprint(body)
        cached = self.store.cached(device["id"], op, digest)
        if cached is not None:
            return cached
        client = None
        if mode != "fixture":
            if not audio and not text.strip():
                raise GadgetError("invalid_request", "A live turn requires text or recorded audio.")
            client = self.backends.client(mode, persona)
            caps = client.capabilities()["capabilities"]
            if "chat" not in caps or (audio and "stt" not in caps) or (body.get("speak") and "tts" not in caps):
                raise GadgetError("capability_disabled", "This published persona lacks a requested chat or speech capability.", 403)
            if trigger and ("commands" not in caps or trigger not in [c.get("trigger") for c in client.commands()]):
                raise GadgetError("command_unavailable", "Command is not enabled on the published persona.", 403)
        cached = self.store.reserve(device["id"], op, digest)
        if cached is not None:
            return cached
        try:
            if mode == "fixture":
                facts = body.get("facts", read_json(self.catalog.path(persona) / "fixture.json"))
                result = evaluate(m, facts)
            else:
                if audio:
                    text = client.transcribe(audio, mime=body.get("audioMime", "audio/wav"))
                user = "gadget:" + device["id"]
                session = self.store.session(device["id"], persona, mode)
                if trigger:
                    result = {"status": "command_result", "command": trigger,
                              "result": client.command(trigger, text, user, session),
                              "review": "Use the authenticated Persona app for protected actions."}
                else:
                    result = client.chat(text, user, session, image_url=image)
                    self.store.save_session(device["id"], persona, mode, result.get("sessionId"))
                result.update({"mode": mode, "persona": persona})
                if body.get("speak") and result.get("text"):
                    try:
                        speech = client.speak(result["text"], audio_format)
                        result["audio"] = {"mime": "audio/wav" if audio_format == "wav" else "audio/mpeg",
                                           "base64": base64.b64encode(speech).decode()}
                    except GadgetError:
                        # Preserve the completed text response; retrying the whole turn could duplicate effects.
                        result["speechError"] = "Reply completed; speech generation failed. Do not replay the turn."
            result["operationId"] = op
            self.store.finish(device["id"], op, result)
            return result
        except Exception:
            self.store.fail(device["id"], op)
            raise


def make_server(bridge, host="127.0.0.1", port=8765, cert=None, key=None):
    if host not in ("127.0.0.1", "localhost", "::1") and not (cert and key):
        raise GadgetError("tls_required", "LAN binding requires --cert and --key.")
    web = Path(__file__).parent / "web"

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            # Do not log bearer tokens, URLs, prompts, audio or private results.
            pass

        def send(self, status, data, mime="application/json"):
            raw = json.dumps(data, allow_nan=False).encode() if mime == "application/json" else data
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def read_body(self):
            if self.headers.get("Transfer-Encoding"):
                raise GadgetError("invalid_request", "Chunked request bodies are not accepted.")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise GadgetError("invalid_request", "Invalid Content-Length.") from exc
            if not 0 < length <= MAX_BODY:
                raise GadgetError("request_too_large", "Request must be nonempty and at most 3 MiB.", 413)
            self.connection.settimeout(30)
            try:
                value = json.loads(self.rfile.read(length), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                if not isinstance(value, dict):
                    raise ValueError()
                return value
            except (ValueError, OSError) as exc:
                raise GadgetError("invalid_json", "Expected a complete JSON object with finite numbers.") from exc

        def device(self):
            header = self.headers.get("Authorization", "")
            return bridge.store.authenticate(header[7:] if header.startswith("Bearer ") else "")

        def dispatch(self, method):
            u = urlsplit(self.path)
            if method == "GET" and u.path in ("/", "/app.js", "/controls.js", "/style.css", "/favicon.svg"):
                file = web / ("index.html" if u.path == "/" else u.path[1:])
                mime = "text/html; charset=utf-8" if u.path == "/" else (
                    "image/svg+xml" if u.path.endswith("svg") else "text/css" if u.path.endswith("css") else "text/javascript")
                return self.send(200, file.read_bytes(), mime)
            portrait = PORTRAIT.fullmatch(u.path) if method == "GET" else None
            if portrait:
                file = bridge.catalog.path(portrait.group(1)) / "portrait.jpg"
                if not file.is_file():
                    raise GadgetError("not_found", "Portrait not found.", 404)
                return self.send(200, file.read_bytes(), "image/jpeg")
            if method == "GET" and u.path == "/health":
                return self.send(200, {"status": "ok", "protocolVersion": 1})
            device = self.device()
            if method == "GET" and u.path == "/v1/catalog":
                return self.send(200, {"protocolVersion": 1, "personas": bridge.catalog.public(device["personas"])})
            if method == "GET" and u.path == "/v1/capabilities":
                q = parse_qs(u.query)
                return self.send(200, bridge.capabilities(device, q.get("persona", [""])[0], q.get("backend", ["fixture"])[0]))
            if method == "GET" and u.path.startswith("/v1/turns/"):
                op = u.path[len("/v1/turns/"):]
                if not OPERATION.fullmatch(op):
                    raise GadgetError("invalid_operation", "Invalid operation ID.")
                return self.send(200, bridge.store.receipt(device["id"], op))
            if method == "POST" and u.path == "/v1/turns":
                return self.send(200, bridge.turn(device, self.read_body()))
            if method == "POST" and u.path == "/v1/reviews":
                body = self.read_body()
                return self.send(200, bridge.store.review_fixture(device["id"], body.get("operationId"),
                                 body.get("revision"), body.get("decision")))
            raise GadgetError("not_found", "Endpoint not found.", 404)

        def handle_request(self, method):
            try:
                self.dispatch(method)
            except GadgetError as exc:
                self.close_connection = True
                self.send(exc.status, {"error": {"code": exc.code, "message": str(exc)}})
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except Exception:
                self.close_connection = True
                self.send(500, {"error": {"code": "internal_error", "message": "Bridge operation failed; do not replay uncertain turns."}})

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    if cert and key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
