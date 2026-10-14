"""Copy validated source examples to installable package data."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gabriel_gadget.packs import validate_pack

for source in sorted((ROOT / "examples/personas").iterdir()):
    if source.is_dir():
        validate_pack(source)
        target = ROOT / "src/gabriel_gadget/packs" / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
print("Source examples synchronized to package data.")
