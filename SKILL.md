---
name: gabriel-persona-gadget
description: Build a custom Gabriel persona gadget using the device SDK, portable example packages, Linux bridge and ESP32 firmware.
---

# Build a persona gadget

Read AGENTS.md, README.md, docs/protocol.md and docs/custom-personas.md first.
Identify the profession, source evidence, review boundary, device input/output
capabilities and execution choice: fixture, Gabriel Cloud, or an existing LAN
Portable Runtime appliance. Inspect an existing example before scaffolding.

Use `gabriel-gadget scaffold` for a custom package. Keep persona definitions,
ontology and synthetic fixtures in the package; credentials, recordings, user
records and receipt state stay outside Git. Fixture engines are bounded built-ins,
not code loaded from untrusted packages. Cloud/local behavior belongs to the
published persona and its installed capabilities.

For live setup, use the user's already authorized Gabriel authoring connection
to create/configure/publish if needed. Mint a persona-scoped runtime token; keep
workspace administration credentials out of gadgets. Save secrets through the
user's secret manager or a private local environment file without printing them.
Configure expected published persona IDs and token environment variable names.

Enroll a device for the intended persona IDs and save its credential privately.
Use HTTPS and an explicitly trusted CA on LAN. Do not disable certificate
verification. Reuse stable operation IDs and receipt recovery; never replay an
uncertain protected request automatically. Demo review never authorizes a live
effect. Use the authenticated Persona app for actual protected approvals.

Run SDK/domain tests, validate all packages, verify source/package parity and
publication hygiene, and build the affected firmware profile. Record fixture,
API-contract, live-provider and physical-hardware evidence separately. Never
claim that a mocked reply or compile pass proves a real hardware or domain trial.
