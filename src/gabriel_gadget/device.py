"""Linux, simulator and custom-device client for the v1 bridge protocol."""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from .backend import NoRedirect, validate_origin
from .errors import GadgetError


class Device:
    def __init__(self, origin, token, ca_file=None, allow_loopback_http=False):
        self.origin = validate_origin(origin, "cloud", allow_loopback_http)
        self.token = token
        if not token.startswith("gdev_") or any(c.isspace() for c in token):
            raise GadgetError("device_token_required", "A device token is required.")
        self.opener = urllib.request.build_opener(urllib.request.HTTPSHandler(
            context=ssl.create_default_context(cafile=ca_file)), NoRedirect())

    def request(self, path, body=None):
        req = urllib.request.Request(self.origin + path,
                  data=json.dumps(body, allow_nan=False).encode() if body is not None else None,
                  headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(req, timeout=120) as response:
                raw = response.read(12 * 1024 * 1024 + 1)
                if len(raw) > 12 * 1024 * 1024:
                    raise GadgetError("response_too_large", "Device response exceeds the limit.", 502)
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read(65536))["error"]
            except (ValueError, KeyError, TypeError):
                error = {"code": "bridge_rejected", "message": "Bridge rejected the request."}
            raise GadgetError(error["code"], error["message"], exc.code) from exc
        except urllib.error.URLError as exc:
            raise GadgetError("bridge_unreachable", "Bridge unavailable; retain the operation ID and inspect before retrying.", 503) from exc

    def catalog(self):
        return self.request("/v1/catalog")["personas"]

    def capabilities(self, persona, backend="fixture"):
        return self.request("/v1/capabilities?" + urllib.parse.urlencode({"persona": persona, "backend": backend}))

    def turn(self, persona, operation_id, backend="fixture", **payload):
        return self.request("/v1/turns", {"persona": persona, "operationId": operation_id,
                                        "backend": backend, **payload})

    def review(self, operation_id, revision, decision):
        return self.request("/v1/reviews", {"operationId": operation_id, "revision": revision, "decision": decision})

    def receipt(self, operation_id):
        return self.request("/v1/turns/" + urllib.parse.quote(operation_id, safe=""))
