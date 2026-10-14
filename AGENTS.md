# Working on the gadget SDK

Work in the primary checkout on main unless explicitly requested otherwise.
Keep real credentials, device tokens, recordings, participant data and runtime
state out of Git. Never copy the private Gabriel backend into this repository.

The 14 example packs are synthetic demonstrations, not production exports or
certification. Preserve domain approval boundaries and clearly distinguish
fixture, HTTP-contract, live-provider and physical-hardware evidence.

Always use shared styled form controls. The simulator's primitives live in
src/gabriel_gadget/web/controls.js: inputField, textareaField and selectField.
Never add raw feature-level input, textarea, select, checkbox/radio or disclosure
widgets. Extend a shared primitive when a capability is missing, preserving
accessible labels, keyboard navigation, disabled states and credential masking.
scripts/verify_distribution.py audits controls outside these primitives.

Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`,
`PYTHONPATH=src python3 -m gabriel_gadget validate`, and
`PYTHONPATH=src python3 scripts/verify_distribution.py` before delivery.
Firmware changes also require the ESP-IDF build matrix. Never flash a board or
run a protected external effect without authorization for that particular action.

New persona packs must include persona.json, assets/chat-config.json,
assets/ontology.json, a fixture, an expected result, scenario checks and a README.
The package data under src/gabriel_gadget/packs must match examples/personas.
Use scripts/sync_packs.py after authoring examples.
