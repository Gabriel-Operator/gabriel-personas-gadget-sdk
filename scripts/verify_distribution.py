"""Check shipped example parity and publication hygiene without private sources."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gabriel_gadget.cli import validate
from gabriel_gadget.packs import Catalog

expected = {"lane", "sherma", "nest", "juno", "lina", "kai", "emil", "nora", "archer", "cole", "boli", "chakri", "paya", "mirav"}
catalog = Catalog()
assert set(catalog.names()) == expected, "Installed examples must contain all 14 personas"
validate(catalog)
for name in sorted(expected):
    source = ROOT / "examples/personas" / name
    packaged = catalog.path(name)
    source_files = {str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()}
    target_files = {str(p.relative_to(packaged)) for p in packaged.rglob("*") if p.is_file()}
    assert source_files == target_files, "File parity failed: " + name
    for relative in source_files:
        assert (source / relative).read_bytes() == (packaged / relative).read_bytes(), "Content parity failed: " + name + "/" + relative
assert (ROOT / "LICENSE").is_file(), "License missing"
for folder in (ROOT / "src", ROOT / "examples", ROOT / "esp32", ROOT / "docs"):
    for file in folder.rglob("*"):
        if not file.is_file() or file.suffix not in (".py", ".json", ".md", ".html", ".js", ".c", ".h", ".yml", ".yaml"):
            continue
        text = file.read_text()
        assert not re.search(r"/Users/[^/\s]+/", text), "Private machine path in " + str(file.relative_to(ROOT))
        assert not re.search(r"(?:gh[op]_|sk-proj-)[A-Za-z0-9_-]{20,}", text), "Possible credential in " + str(file.relative_to(ROOT))
for file in (ROOT / "src/gabriel_gadget/web").glob("*"):
    if file.name != "controls.js":
        assert not re.search(r"<(?:input|textarea|select|details|summary)\b|createElement\(['\"](?:input|textarea|select)['\"]\)", file.read_text()), "Native form control outside shared controls"
print(json.dumps({"packages": 14, "sourcePackageParity": True, "scenarioChecks": "passed", "publicationHygiene": "passed"}))
