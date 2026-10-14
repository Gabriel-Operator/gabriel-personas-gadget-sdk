"""Direct Persona API transport for hosted or LAN appliance execution."""
import ipaddress
import json
import mimetypes
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .errors import BackendError, GadgetError

MAX_RESPONSE = 8 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_origin(origin, mode, allow_loopback_http=False):
    u = urllib.parse.urlsplit(origin)
    if not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ("", "/"):
        raise GadgetError("invalid_origin", "Backend origin must be a plain origin without credentials or paths.")
    if u.scheme != "https":
        if not (allow_loopback_http and u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1")):
            raise GadgetError("tls_required", "HTTPS is required; HTTP is available only for explicit loopback development.")
    if mode == "local":
        try:
            addresses = {entry[4][0] for entry in socket.getaddrinfo(u.hostname, u.port or 443)}
        except OSError as exc:
            raise GadgetError("local_unreachable", "Cannot resolve local appliance.", 503) from exc
        if not addresses or any(not (ipaddress.ip_address(a).is_private or ipaddress.ip_address(a).is_loopback)
                                for a in addresses):
            raise GadgetError("local_origin_required", "Local mode requires a private LAN or loopback appliance.")
    return origin.rstrip("/")


class GabrielPersona:
    """Small stdlib Persona API client. Never retries a POST automatically.

    This uses Gabriel's documented direct HTTP interface. Realtime audio and
    workspace administration are intentionally absent from this transport.
    """

    def __init__(self, origin, token, persona_id, mode="cloud", ca_file=None,
                 allow_loopback_http=False, timeout=60, client_cert=None, client_key=None):
        self.origin = validate_origin(origin, mode, allow_loopback_http)
        if not token or not token.startswith("gabi_") or any(c.isspace() for c in token):
            raise GadgetError("persona_token_required", "A persona-scoped token is required.")
        if not isinstance(persona_id, str) or not persona_id:
            raise GadgetError("persona_binding_required", "Configure the expected published persona ID.")
        self.token = token
        self.mode = mode
        self.persona_id = persona_id
        self.timeout = timeout
        context = ssl.create_default_context(cafile=ca_file)
        if bool(client_cert) != bool(client_key):
            raise GadgetError("client_certificate_required", "Supply both appliance client certificate and private key.")
        if client_cert:
            context.load_cert_chain(client_cert, client_key)
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())
        download_context = ssl.create_default_context()
        if ca_file:
            download_context.load_verify_locations(cafile=ca_file)
        self.download_opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=download_context), NoRedirect())

    def _open(self, path, body=None, content_type="application/json", headers=None):
        req = urllib.request.Request(self.origin + "/api/v1" + path, data=body,
                                     headers={"Authorization": "Bearer " + self.token,
                                              "Accept": "application/json",
                                              **({"Content-Type": content_type} if body is not None else {}),
                                              **(headers or {})})
        try:
            return self.opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise BackendError("rate_limited", "Persona rate limited; respect Retry-After and review before retrying.", 429) from exc
            raise BackendError("backend_rejected", "Persona API rejected the request (HTTP %s)." % exc.code, 502) from exc
        except (OSError, urllib.error.URLError) as exc:
            raise BackendError("backend_unreachable", "Persona API is unreachable; the bridge will not replay this turn.", 503) from exc

    def _json(self, path, payload=None):
        body = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        with self._open(path, body) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise BackendError("response_too_large", "Persona API response exceeds the device bridge limit.", 502)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except ValueError as exc:
            raise BackendError("invalid_backend_response", "Persona API returned invalid JSON.", 502) from exc

    def capabilities(self):
        body = self._json("/models")
        models = body.get("data", [])
        if len(models) != 1 or models[0].get("id") != "gabriel/" + self.persona_id:
            raise BackendError("persona_binding_mismatch", "Token is bound to a different published persona.", 403)
        model = models[0]
        return {"personaId": self.persona_id, "name": model.get("name", self.persona_id),
                "capabilities": model.get("capabilities", ["chat"])}

    def chat(self, text, user, session_id=None, image_url=None):
        content = text if not image_url else [{"type": "text", "text": text},
                                              {"type": "image_url", "image_url": {"url": image_url}}]
        body = self._json("/chat/completions", {"messages": [{"role": "user", "content": content}],
                     "user": user, "stream": False,
                     **({"metadata": {"session_id": session_id}} if session_id else {})})
        g = body.get("gabriel", {})
        try:
            answer = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BackendError("invalid_backend_response", "Missing persona reply.", 502) from exc
        return {"status": "reply", "text": answer, "sessionId": g.get("session_id") or g.get("sessionId"),
                "events": g.get("events", []), "review": "Use the authenticated Persona app for protected actions."}

    def chat_stream(self, text, user, session_id=None):
        payload = {"messages": [{"role": "user", "content": text}], "user": user, "stream": True,
                   **({"metadata": {"session_id": session_id}} if session_id else {})}
        with self._open("/chat/completions", json.dumps(payload).encode(),
                        headers={"Accept": "text/event-stream"}) as response:
            data_lines = []
            total = 0
            while True:
                raw = response.readline(65537)
                if not raw:
                    raise BackendError("stream_interrupted", "Stream ended before [DONE]; do not replay automatically.", 502)
                total += len(raw)
                if len(raw) > 65536 or total > MAX_RESPONSE:
                    raise BackendError("response_too_large", "Stream exceeds device limits.", 502)
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif not line and data_lines:
                    payload = "\n".join(data_lines)
                    data_lines = []
                    if payload == "[DONE]":
                        return
                    chunk = json.loads(payload)
                    if chunk.get("error"):
                        raise BackendError("stream_failed", "Persona stream failed.", 502)
                    yield chunk

    def commands(self):
        # The server's list response uses data, not commands.
        return self._json("/commands").get("data", [])

    def command(self, trigger, text, user, session_id=None):
        return self._json("/commands/" + urllib.parse.quote(trigger, safe=""),
                          {"input": text, "user": user,
                           **({"metadata": {"session_id": session_id}} if session_id else {})})

    def transcribe(self, data, filename="voice.wav", mime="audio/wav"):
        boundary = "gabriel-" + uuid.uuid4().hex
        safe_name = "voice" + (mimetypes.guess_extension(mime) or ".bin")
        body = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
                "Content-Type: %s\r\n\r\n" % (boundary, safe_name, mime)).encode() + data
        body += ("\r\n--%s--\r\n" % boundary).encode()
        with self._open("/audio/transcriptions", body, "multipart/form-data; boundary=" + boundary) as response:
            raw = response.read(MAX_RESPONSE + 1)
        try:
            text = json.loads(raw)["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError()
            return text
        except (ValueError, KeyError, TypeError) as exc:
            raise BackendError("invalid_transcript", "Speech provider returned no usable transcript.", 502) from exc

    def speak(self, text, audio_format="mp3"):
        if audio_format not in ("mp3", "wav"):
            raise GadgetError("invalid_audio_format", "Choose mp3 or wav for reply audio.")
        try:
            response = self._open("/audio/speech", json.dumps({"input": text, "response_format": audio_format}).encode())
        except BackendError as exc:
            cause = exc.__cause__
            if not isinstance(cause, urllib.error.HTTPError) or cause.code not in (301, 302, 303, 307, 308):
                raise
            url = urllib.parse.urljoin(self.origin, cause.headers.get("Location", ""))
            u = urllib.parse.urlsplit(url)
            if u.scheme != "https" or not u.hostname or u.username or u.password:
                raise BackendError("unsafe_audio_redirect", "Speech returned an unsafe download URL.", 502) from exc
            if self.mode == "local":
                validate_origin(u.scheme + "://" + u.netloc, "local")
            # The provider URL gets no Gabriel Authorization header. No additional redirects.
            try:
                response = self.download_opener.open(urllib.request.Request(url), timeout=self.timeout)
            except (OSError, urllib.error.URLError) as error:
                raise BackendError("speech_download_failed", "Speech download failed.", 502) from error
        with response:
            data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE:
            raise BackendError("audio_too_large", "Speech response exceeds device limits.", 502)
        if audio_format == "wav" and (len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE"):
            raise BackendError("speech_format_unavailable", "Provider did not return WAV audio for the embedded speaker.", 502)
        return data


class Backends:
    def __init__(self, config=None):
        self.config = config or {"profiles": {"fixture": {}}}

    def client(self, mode, persona):
        if mode not in ("cloud", "local"):
            raise GadgetError("invalid_backend", "Choose fixture, cloud, or local.")
        profile = self.config.get("profiles", {}).get(mode, {})
        binding = profile.get("bindings", {}).get(persona, {})
        env_name = binding.get("tokenEnv", "")
        token = os.environ.get(env_name, "") if env_name else ""
        if not profile.get("origin") or not token or not binding.get("personaId"):
            raise GadgetError("backend_not_configured", "Configure this persona's backend binding and token environment variable.", 503)
        return GabrielPersona(profile["origin"], token, binding["personaId"], mode,
                              ca_file=profile.get("caFile"), allow_loopback_http=profile.get("allowLoopbackHttp", False),
                              client_cert=profile.get("clientCertFile"), client_key=profile.get("clientKeyFile"))
