# Paya on a gadget

Time-sensitive online buying windows.

Run `gabriel-gadget demo paya` after installing the SDK, or use the checkout command `PYTHONPATH=src python3 -m gabriel_gadget demo paya`.

The fixture, offers, sources and participants are synthetic. `expected.json` is the reproducible complete result; `scenarios.json` declares domain acceptance checks. No model or external account is required.

**Boundary:** Verify seller, stock, total and expiry. A changed plan invalidates approval; only the cardholder approves purchase.

For a connected example, publish your persona, enable the needed capabilities, configure a persona-scoped backend binding, and use the same device API with `backend: cloud` or `backend: local`. The sample chat-config uses explanation-only commands; it does not import the production operators. Existing production personas can be connected directly, but command triggers must match their enabled `/commands` response.

Full experience prerequisites: Fresh seller, stock and pricing; Reliable schedule owner; Exact-plan cardholder approval.

The portable ontology is an example vocabulary, not production operational data. See the root documentation for cloud provisioning, local-appliance setup and physical-hardware validation boundaries.
