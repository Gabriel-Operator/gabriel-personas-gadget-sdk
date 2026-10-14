# Boli on a gadget

Adult-guided learning for ages 9–18.

Run `gabriel-gadget demo boli` after installing the SDK, or use the checkout command `PYTHONPATH=src python3 -m gabriel_gadget demo boli`.

The fixture, offers, sources and participants are synthetic. `expected.json` is the reproducible complete result; `scenarios.json` declares domain acceptance checks. No model or external account is required.

**Boundary:** Stay inside the course and learner age. Record observations without awarding mastery; an adult reviews learning evidence.

For a connected example, publish your persona, enable the needed capabilities, configure a persona-scoped backend binding, and use the same device API with `backend: cloud` or `backend: local`. The sample chat-config uses explanation-only commands; it does not import the production operators. Existing production personas can be connected directly, but command triggers must match their enabled `/commands` response.

Full experience prerequisites: Local or connected speech models for voice; Authenticated adult review; School reporting integration.

The portable ontology is an example vocabulary, not production operational data. See the root documentation for cloud provisioning, local-appliance setup and physical-hardware validation boundaries.
