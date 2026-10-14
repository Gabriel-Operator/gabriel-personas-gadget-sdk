# Mirav on a gadget

![Mirav](portrait.jpg)

Official portrait: [Mirav](https://gabrieloperator.com/persona/mirav).

Nearby family activities and introductions.

Run `gabriel-gadget demo mirav` after installing the SDK, or use the checkout command `PYTHONPATH=src python3 -m gabriel_gadget demo mirav`.

The fixture, offers, sources and participants are synthetic. `expected.json` is the reproducible complete result; `scenarios.json` declares domain acceptance checks. No model or external account is required.

**Boundary:** Use only explicitly enabled location scope. Keep precise locations private and wait for mutual consent.

For a connected example, publish your persona, enable the needed capabilities, configure a persona-scoped backend binding, and use the same device API with `backend: cloud` or `backend: local`. The sample chat-config uses explanation-only commands; it does not import the production operators. Existing production personas can be connected directly, but command triggers must match their enabled `/commands` response.

Full experience prerequisites: Authorized location input; Private participant service; Mutual authenticated consent.

The portable ontology is an example vocabulary, not production operational data. See the root documentation for cloud provisioning, local-appliance setup and physical-hardware validation boundaries.
