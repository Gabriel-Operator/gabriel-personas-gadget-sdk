# Sherma on a gadget

Official and operational forms.

Run `gabriel-gadget demo sherma` after installing the SDK, or use the checkout command `PYTHONPATH=src python3 -m gabriel_gadget demo sherma`.

The fixture, offers, sources and participants are synthetic. `expected.json` is the reproducible complete result; `scenarios.json` declares domain acceptance checks. No model or external account is required.

**Boundary:** Prepare a form twin and request missing records. Never submit the live form without exact-plan approval.

For a connected example, publish your persona, enable the needed capabilities, configure a persona-scoped backend binding, and use the same device API with `backend: cloud` or `backend: local`. The sample chat-config uses explanation-only commands; it does not import the production operators. Existing production personas can be connected directly, but command triggers must match their enabled `/commands` response.

Full experience prerequisites: Real form/browser adapter; Authenticated applicant records; Submission approval.

The portable ontology is an example vocabulary, not production operational data. See the root documentation for cloud provisioning, local-appliance setup and physical-hardware validation boundaries.
