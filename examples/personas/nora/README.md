# Nora on a gadget

![Nora](portrait.jpg)

Official portrait: [Nora](https://gabrieloperator.com/persona/nora).

Banking operations preparation.

Run `gabriel-gadget demo nora` after installing the SDK, or use the checkout command `PYTHONPATH=src python3 -m gabriel_gadget demo nora`.

The fixture, offers, sources and participants are synthetic. `expected.json` is the reproducible complete result; `scenarios.json` declares domain acceptance checks. No model or external account is required.

**Boundary:** Show policy, source documents and exceptions. Only authorized bankers approve banking actions.

For a connected example, publish your persona, enable the needed capabilities, configure a persona-scoped backend binding, and use the same device API with `backend: cloud` or `backend: local`. The sample chat-config uses explanation-only commands; it does not import the production operators. Existing production personas can be connected directly, but command triggers must match their enabled `/commands` response.

Full experience prerequisites: Bank-controlled identity; Bank policy and system adapters; Authenticated banker approval.

The portable ontology is an example vocabulary, not production operational data. See the root documentation for cloud provisioning, local-appliance setup and physical-hardware validation boundaries.
