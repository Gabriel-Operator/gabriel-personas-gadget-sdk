"""Validated, portable persona packages; definitions never carry credentials."""
import hashlib
import json
import re
from pathlib import Path

from .errors import GadgetError

ID = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
PACK_ROOT = Path(__file__).parent / "packs"
SECRET = re.compile(r"(?:gabi_|gdev_|sk-proj-|gh[op]_)[A-Za-z0-9_-]{12,}")
REQUIRED = ("persona.json", "assets/chat-config.json", "assets/ontology.json",
            "fixture.json", "expected.json", "scenarios.json", "README.md")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise GadgetError("invalid_package", "Package contains missing or invalid JSON.") from exc


def validate_pack(path):
    path = Path(path)
    if path.is_symlink():
        raise GadgetError("invalid_package", "Package symlinks are not permitted.")
    missing = [name for name in REQUIRED if not (path / name).is_file()]
    if missing:
        raise GadgetError("invalid_package", "Missing package files: " + ", ".join(missing))
    for file in path.rglob("*"):
        if file.is_symlink():
            raise GadgetError("invalid_package", "Package symlinks are not permitted.")
        if file.is_file():
            text = file.read_text()
            if SECRET.search(text) or "/Users/" in text or "localhost:3200" in text:
                raise GadgetError("private_definition", "Package contains credentials or private machine references.")
    manifest = read_json(path / "persona.json")
    if manifest.get("schemaVersion") != 1 or not ID.fullmatch(manifest.get("id", "")):
        raise GadgetError("invalid_package", "Expected schemaVersion 1 and a portable persona ID.")
    for key in ("name", "domain", "systemPrompt", "boundary", "fixtureEngine"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise GadgetError("invalid_package", "Missing manifest field: " + key)
    if manifest.get("fixtureEngine") not in {
        "lane", "sherma", "nest", "juno", "lina", "kai", "emil", "nora",
        "archer", "cole", "boli", "chakri", "paya", "mirav", "custom",
    }:
        raise GadgetError("invalid_package", "Unsupported fixture engine.")
    if not isinstance(manifest.get("commands"), list) or not all(
        isinstance(c, str) and ID.fullmatch(c) for c in manifest["commands"]
    ):
        raise GadgetError("invalid_package", "Commands must be portable trigger names.")
    config = read_json(path / "assets/chat-config.json")
    if config.get("publishedConfig", {}).get("systemPrompt") != manifest["systemPrompt"]:
        raise GadgetError("invalid_package", "Manifest and authored chat prompt differ.")
    if not read_json(path / "scenarios.json").get("checks"):
        raise GadgetError("invalid_package", "Every package must declare scenario checks.")
    return manifest


class Catalog:
    def __init__(self, root=PACK_ROOT):
        self.root = Path(root)

    def names(self):
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and (p / "persona.json").exists())

    def path(self, persona):
        if not isinstance(persona, str) or not ID.fullmatch(persona):
            raise GadgetError("unknown_persona", "Invalid persona ID.", 404)
        path = self.root / persona
        if not path.is_dir():
            raise GadgetError("unknown_persona", "Persona package not found.", 404)
        return path

    def get(self, persona):
        return validate_pack(self.path(persona))

    def public(self, names=None):
        return [{k: self.get(name)[k] for k in ("id", "name", "domain", "boundary", "commands")}
                for name in (names if names is not None else self.names())]
