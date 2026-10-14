# Architecture and release boundary

```
ESP32 / Linux device / browser simulator
    device-scoped credential, persona ID, stable operation ID
                      │
             HTTPS device protocol v1
                      │
              Python device bridge
      ┌───────────────┼─────────────────┐
      │               │                 │
synthetic engine   Gabriel Cloud    LAN Portable Runtime
 no model or WAN   Persona API      same Persona API
 no external      published token   local published token
 effects                            local inference/tools
```

The bridge owns credential lookup, capability discovery, device/persona/session
partitioning, durable request receipts, and audio format conversion. Device
credentials are hashed in a private SQLite database. Backend tokens are supplied
through environment variables. The SDK never accepts a provider URL or credential
from a gadget request.

Packages are authored definitions. Sessions, receipt state, recordings, review
decisions and live results are private runtime data. `fixtureEngine` chooses a
bounded built-in deterministic demonstration; it never imports package code.
The portable example ontology names the domain vocabulary. The fixture results
show provenance and approval boundaries without inventing accepted economic value.

The live transport implements Gabriel's documented `/api/v1` interface directly
with Python's standard library so the basic installation has no dependencies.
It supports `/models`, chat/SSE, command discovery and invocation, multipart
transcription and batch speech. It does not reimplement workspace administration,
the persona harness, Signals, SaaS connectors or arbitrary local tool execution.

All gadgets use the same protocol regardless of persona or execution profile.
The 14 examples can share an inference backend; they do not need 14 model weights.
ESP32 is a peripheral. A Raspberry Pi is a supported Linux client/bridge candidate,
not a verified host for Gabriel's current full GPU appliance.

Protected live effects retain the backend's governance and authenticated review
surface. A device credential does not create human authority, and a device/user
session label does not substitute for end-user authentication. v0.1 is intended
for devices controlled by the owner of the configured backend bindings.

## Separate future commitments

- An independently buildable and licensed open-source persona execution runtime.
- Shared household/school user authentication and delegated device grants.
- Board-specific displays, ES7210/ES8311 codecs, cameras, power measurements and signed OTA.
- Registered permissioned actuator/sensor dispatch; chat event text is never executed as a hardware command.
- Live-provider domain acceptance and actual WAN-disconnected appliance/hardware trials.

Source references: Gabriel's gateway documentation and Persona API implementation;
Muse's published SDK architecture; vendor hardware specifications. This repository
publishes an original client and synthetic examples, not the private backend.
