"""Opt-in live chat checks using owner's configured persona bindings.

Use chat-only scoped tokens. This does not invoke command or approval endpoints.
It records real model responses separately from fixture/contract evidence.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gabriel_gadget.backend import Backends
from gabriel_gadget.errors import GadgetError
from gabriel_gadget.packs import Catalog, read_json

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--config", type=Path, required=True)
p.add_argument("--backend", choices=("cloud", "local"), required=True)
p.add_argument("--personas", default="boli,kai,chakri")
p.add_argument("--output", type=Path, required=True)
args = p.parse_args()
backends = Backends(read_json(args.config))
catalog = Catalog()
results = []
for name in args.personas.split(","):
    try:
        manifest = catalog.get(name)
        client = backends.client(args.backend, name)
        capabilities = client.capabilities()
        facts = read_json(catalog.path(name) / "fixture.json")
        prompt = ("This is a synthetic acceptance example. Explain the prepared proposal and review boundary "
                  "using these facts only. Do not call tools, send messages, submit forms, buy, publish, "
                  "dispatch or move money. " + manifest["examplePrompt"] + "\n" + json.dumps(facts))
        result = client.chat(prompt, "gadget-live-acceptance")
        results.append({"persona": name, "backend": args.backend, "transport": "passed",
                        "capabilities": capabilities["capabilities"], "reply": result["text"],
                        "humanDomainReview": "required", "physicalHardware": "not exercised"})
    except GadgetError as exc:
        results.append({"persona": name, "backend": args.backend, "transport": "failed", "errorCode": exc.code})
report = {"asOf": datetime.now(timezone.utc).isoformat(), "evidenceType": "live-chat",
          "note": "Responses are real provider output; human domain acceptance and physical trials remain separate.", "results": results}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"report": str(args.output), "passed": sum(x["transport"] == "passed" for x in results), "total": len(results)}))
raise SystemExit(0 if all(x["transport"] == "passed" for x in results) else 1)
