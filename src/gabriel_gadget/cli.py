import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .backend import Backends
from .bridge import Bridge, make_server
from .device import Device
from .errors import GadgetError
from .fixtures import evaluate
from .packs import Catalog, ID, read_json, validate_pack
from .store import Store


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))


def validate(catalog):
    report = []
    for name in catalog.names():
        manifest = catalog.get(name)
        path = catalog.path(name)
        result = evaluate(manifest, read_json(path / "fixture.json"))
        if result != read_json(path / "expected.json"):
            raise GadgetError("scenario_failed", "Complete fixture result differs for " + name)
        for key, expected in read_json(path / "scenarios.json")["checks"].items():
            if result.get(key) != expected:
                raise GadgetError("scenario_failed", name + " failed " + key)
        report.append({"persona": name, "status": "passed", "mode": "fixture"})
    return {"packages": len(report), "scenarios": report, "physicalHardware": "not tested by this command"}


def scaffold(destination, persona_id, name, domain, boundary):
    if not ID.fullmatch(persona_id):
        raise GadgetError("invalid_persona", "Use a lowercase portable persona ID.")
    destination = Path(destination)
    if destination.exists():
        raise GadgetError("destination_exists", "Choose a new destination; existing packages are never overwritten.")
    destination.mkdir(parents=True)
    prompt = "You are " + name + ", a persona for " + domain + ". " + boundary
    manifest = {"schemaVersion": 1, "id": persona_id, "name": name, "domain": domain,
                "systemPrompt": prompt, "boundary": boundary, "fixtureEngine": "custom", "commands": [],
                "examplePrompt": "Prepare a reviewable task for " + domain}
    facts = {"task": "Prepare a synthetic example for " + domain, "source": "fixture://custom-task"}
    objects = {"persona.json": manifest, "fixture.json": facts, "expected.json": evaluate(manifest, facts),
        "scenarios.json": {"checks": {"status": "review_required", "actionPerformed": False, "externalEffects": []}},
        "assets/chat-config.json": {"schemaVersion": 1, "resourceKey": "persona.gadget." + persona_id,
                                   "publishedConfig": {"name": name, "systemPrompt": prompt}},
        "assets/ontology.json": {"schemaVersion": 1, "resourceKey": "ontology.gadget." + persona_id,
                                 "name": name, "version": 1, "status": "draft", "entities": [], "relationships": []}}
    for relative, obj in objects.items():
        file = destination / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(obj, indent=2) + "\n")
    (destination / "README.md").write_text("# " + name + "\n\nSynthetic custom-persona starter. Edit the fixture and domain acceptance cases. "
        "Publish assets/chat-config.json through your authorized Gabriel authoring flow, then configure a persona-scoped "
        "cloud or local binding. The generic custom fixture engine prepares a task; it does not execute your domain tools.\n")
    validate_pack(destination)


def main():
    parser = argparse.ArgumentParser(description="Gabriel persona gadgets: fixture, cloud or local appliance")
    parser.add_argument("--packs", type=Path, help="Persona package directory (defaults to installed examples)")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list")
    sub.add_parser("validate")
    demo = sub.add_parser("demo")
    demo.add_argument("persona", nargs="?", default="boli")
    demo.add_argument("--all", action="store_true")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    serve = sub.add_parser("serve")
    serve.add_argument("--state", type=Path, default=Path(".state"))
    serve.add_argument("--config", type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--cert", type=Path)
    serve.add_argument("--key", type=Path)
    for action in ("enroll", "rotate", "revoke"):
        cmd = sub.add_parser(action)
        cmd.add_argument("device")
        cmd.add_argument("--state", type=Path, default=Path(".state"))
        if action in ("enroll", "rotate"):
            cmd.add_argument("--token-file", type=Path, required=True)
        if action == "enroll":
            cmd.add_argument("--personas", default="boli,kai,chakri")
    for action in ("chat", "capabilities", "voice", "command"):
        cmd = sub.add_parser(action)
        cmd.add_argument("persona")
        cmd.add_argument("--bridge", default="http://127.0.0.1:8765")
        cmd.add_argument("--token-file", type=Path, required=True)
        cmd.add_argument("--ca", type=Path)
        cmd.add_argument("--loopback-dev", action="store_true")
        cmd.add_argument("--backend", choices=("fixture", "cloud", "local"), default="fixture")
        if action != "capabilities":
            cmd.add_argument("--operation-id", default=None)
            cmd.add_argument("--text", default="")
        if action == "chat":
            cmd.add_argument("--image-url")
        if action == "voice":
            cmd.add_argument("--audio-file", type=Path)
            cmd.add_argument("--seconds", type=int, default=4)
            cmd.add_argument("--output", type=Path, default=Path("reply.mp3"))
            cmd.add_argument("--play", action="store_true")
        if action == "command":
            cmd.add_argument("trigger")
    custom = sub.add_parser("scaffold")
    custom.add_argument("destination", type=Path)
    custom.add_argument("--id", required=True)
    custom.add_argument("--name", required=True)
    custom.add_argument("--domain", required=True)
    custom.add_argument("--boundary", required=True)
    args = parser.parse_args()
    try:
        catalog = Catalog(args.packs) if args.packs else Catalog()
        if args.action == "list":
            emit(catalog.public())
        elif args.action == "validate":
            emit(validate(catalog))
        elif args.action == "demo":
            names = catalog.names() if args.all else [args.persona]
            results = [evaluate(catalog.get(n), read_json(catalog.path(n) / "fixture.json")) for n in names]
            emit(results if args.all else results[0])
        elif args.action == "doctor":
            emit({"python": "available", "packages": len(catalog.names()), "arecord": bool(shutil.which("arecord")),
                  "ffplay": bool(shutil.which("ffplay")), "espIdf": bool(shutil.which("idf.py")),
                  "note": "Audio utilities and ESP-IDF are optional. This is not hardware or provider readiness proof."})
        elif args.action == "serve":
            config = read_json(args.config) if args.config else None
            bridge = Bridge(Store(args.state), catalog, Backends(config))
            server = make_server(bridge, args.host, args.port, args.cert, args.key)
            emit({"bridge": ("https" if args.cert else "http") + "://" + args.host + ":" + str(server.server_port),
                  "protocolVersion": 1, "defaultBackend": "fixture"})
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        elif args.action in ("enroll", "rotate", "revoke"):
            if not ID.fullmatch(args.device):
                raise GadgetError("invalid_device", "Use a lowercase portable device ID.")
            store = Store(args.state)
            if args.action == "revoke":
                store.revoke(args.device)
                emit({"device": args.device, "status": "revoked"})
            else:
                if args.token_file.exists():
                    raise GadgetError("token_file_exists", "Use a new credential file; existing files are never overwritten.")
                names = args.personas.split(",") if args.action == "enroll" else None
                if names:
                    for name in names:
                        catalog.get(name)
                token = store.enroll(args.device, names) if names else store.rotate(args.device)
                args.token_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                fd = os.open(args.token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as file:
                    file.write(token + "\n")
                emit({"device": args.device, "credentialFile": str(args.token_file), "personas": names,
                      "note": "Token saved privately; no secret was printed."})
        elif args.action == "scaffold":
            scaffold(args.destination, args.id, args.name, args.domain, args.boundary)
            emit({"package": str(args.destination), "status": "created"})
        else:
            device = Device(args.bridge, args.token_file.read_text().strip(), args.ca, args.loopback_dev)
            if args.action == "capabilities":
                emit(device.capabilities(args.persona, args.backend))
                return
            op = args.operation_id or uuid.uuid4().hex
            payload = {"text": args.text}
            if args.action == "command":
                payload["command"] = args.trigger
            elif args.action == "chat" and args.image_url:
                payload["imageUrl"] = args.image_url
            elif args.action == "voice":
                if args.backend == "fixture":
                    raise GadgetError("fixture_voice_unavailable", "Choose cloud or local for actual speech.")
                if not 1 <= args.seconds <= 15:
                    raise GadgetError("invalid_recording", "Record between 1 and 15 seconds.")
                if args.audio_file:
                    audio = args.audio_file.read_bytes()
                else:
                    if not shutil.which("arecord"):
                        raise GadgetError("audio_adapter_missing", "Install ALSA arecord or supply --audio-file.")
                    with tempfile.TemporaryDirectory() as temp:
                        recording = Path(temp) / "voice.wav"
                        subprocess.run(["arecord", "-q", "-d", str(args.seconds), "-r", "16000", "-f", "S16_LE",
                                        "-c", "1", str(recording)], check=True)
                        audio = recording.read_bytes()
                payload.update({"audioBase64": base64.b64encode(audio).decode(), "audioMime": "audio/wav", "speak": True})
            result = device.turn(args.persona, op, args.backend, **payload)
            if result.get("audio"):
                args.output.write_bytes(base64.b64decode(result.pop("audio")["base64"]))
                result["speechFile"] = str(args.output)
                if args.play:
                    if not shutil.which("ffplay"):
                        raise GadgetError("audio_adapter_missing", "Reply saved; install ffplay to play it.")
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", str(args.output)], check=True)
            emit(result)
    except (GadgetError, OSError, subprocess.CalledProcessError) as exc:
        emit({"error": {"code": getattr(exc, "code", "local_error"),
                        "message": str(exc) if isinstance(exc, GadgetError) else "Local file or device operation failed."}})
        raise SystemExit(1)
