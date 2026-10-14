import json
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gabriel_gadget.backend import GabrielPersona
from gabriel_gadget.errors import BackendError


class ApplianceTLS(unittest.TestCase):
    """A real local TLS server requiring a client certificate; no provider calls."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)

        def openssl(*args):
            subprocess.run(["openssl", *args], cwd=self.path, check=True, capture_output=True)

        openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem",
                "-days", "1", "-subj", "/CN=Gadget contract test CA",
                "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
        for role in ("server", "client"):
            openssl("req", "-newkey", "rsa:2048", "-nodes", "-keyout", role + ".key", "-out", role + ".csr",
                    "-subj", "/CN=" + ("localhost" if role == "server" else "gadget-test-client"))
            extension = "subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\n" if role == "server" else "extendedKeyUsage=clientAuth\n"
            extension += "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n"
            (self.path / (role + ".ext")).write_text(extension)
            openssl("x509", "-req", "-in", role + ".csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
                    "-out", role + ".pem", "-days", "1", "-extfile", role + ".ext")

        class API(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                data = json.dumps({"data": [{"id": "gabriel/local-boli", "name": "Boli", "capabilities": ["chat"]}]}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), API)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.path / "server.pem", self.path / "server.key")
        context.load_verify_locations(self.path / "ca.pem")
        context.verify_mode = ssl.CERT_REQUIRED
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.origin = "https://127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def test_local_appliance_accepts_trusted_ca_and_paired_client_certificate(self):
        client = GabrielPersona(self.origin, "gabi_tls_contract_placeholder", "local-boli", mode="local",
            ca_file=self.path / "ca.pem", client_cert=self.path / "client.pem", client_key=self.path / "client.key")
        self.assertEqual(client.capabilities()["personaId"], "local-boli")

    def test_local_appliance_refuses_missing_client_certificate(self):
        client = GabrielPersona(self.origin, "gabi_tls_contract_placeholder", "local-boli", mode="local", ca_file=self.path / "ca.pem")
        with self.assertRaises(BackendError):
            client.capabilities()

    def test_untrusted_appliance_certificate_is_not_bypassed(self):
        client = GabrielPersona(self.origin, "gabi_tls_contract_placeholder", "local-boli", mode="local",
            client_cert=self.path / "client.pem", client_key=self.path / "client.key")
        with self.assertRaises(BackendError):
            client.capabilities()
