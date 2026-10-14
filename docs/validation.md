# Validation evidence and limits

The repository maintains distinct evidence categories:

| Category | What it proves | What it does not prove |
| --- | --- | --- |
| Domain fixtures | All 14 deterministic synthetic journeys and boundary checks | Live model quality or production outcomes |
| Shared device interaction | Boli/KAI/Chakri over actual localhost HTTP, full proposal and simulated review | Physical microphone, display or approval hardware |
| API contracts | Cloud/local bindings, capabilities, sessions, commands, SSE and batch audio against a synthetic HTTP API | Actual provider credentials, installed appliance compatibility or billing |
| Firmware builds | ESP-IDF compilation for the basic and external I2S voice profiles | Correct wiring, audio quality, battery life, secure provisioning or physical recovery |
| Installed package | A clean installation carries all 14 example packages | Independent local LLM/harness execution |

Run `scripts/verify_distribution.py` to check source/package parity, complete
fixture results and publication hygiene. The test suite has no external API
credentials and performs no protected external effects.

## Recorded software validation: 2026-10-14

The release preparation completed these checks locally:

- **43 passing Python tests** on Python 3.13.7: all 14 domain examples, real
  localhost HTTP interaction, command/SSE/batch-speech contracts, isolated
  sessions, revocation, revision-bound demo review, concurrent requests and
  persisted receipts. Three tests exercised real TLS certificate verification
  and paired client certificates against a local test server.
- **14 complete packages** passed exact expected-result and scenario checks,
  source/package byte parity and the publication audit. The audit also enforces
  shared styled form primitives in the simulator.
- A clean wheel installation on Python 3.11 validated all 14 bundled examples
  without loading the source checkout. A source archive includes the example
  packages, firmware, dependency lock, guides and contributor scripts.
- The browser simulator completed Boli's adult-review journey, KAI's cited
  280-cent inventory-gap cart, and Chakri's 220-cent rate-card estimate. The
  shared styled picker was checked with pointer and keyboard input, and at a
  390-pixel mobile width. Review produced a synthetic receipt with no external
  effects. [Saved simulator view](images/simulator.jpg).
- Both **basic** and **external I2S voice** ESP32-S3 profiles compiled with the
  official ESP-IDF 6.0.1 container and locked cJSON dependency. This includes
  the encrypted development NVS initialization and pending-operation recovery
  code. No board was flashed.

[Machine-readable evidence](../validation/software.json) records the categories,
commands and local firmware hashes. Hashes identify these local build artifacts;
they are not a claim of reproducible firmware binaries across machines.
GitHub Actions independently runs the Python version and firmware profile matrix
on every push. Consult the workflow result for the exact published revision.

Live Gabriel credentials, an installed appliance and physical board peripherals
were unavailable during these checks. Live-provider, disconnected-WAN appliance
and physical-hardware acceptance therefore remain unperformed. The software
checks establish a reviewable integration baseline.

## Physical/live acceptance to record for a deployment

1. Verify the exact board model/revision, GPIOs, memory and codec adapter.
2. Enroll/provision a device; verify TLS trust and credential revocation.
3. Run Boli, KAI and Chakri through the actual chosen backend, inspect their
   evidence, and test unavailable capabilities and changed approval plans.
4. Record real microphone and speaker behavior, reboot receipt recovery,
   network interruptions, clock recovery, memory use and sustained operation.
5. Test the remaining domain scenarios with authorized live inputs and reviewers.
6. For local acceptance disconnect WAN/DNS and verify that no cloud fallback,
   speech provider or protected action is silently invoked.

Do not weaken assertions, replace live outcomes with fixture outputs, or claim
realized ROI from synthetic prices/time. Physical and live-provider acceptance
remain separate from the software release's deterministic checks.

`scripts/live_acceptance.py` is an opt-in chat-only transport check for configured
bindings. Use chat-only scoped tokens, record output in private `.state`, then
have a domain reviewer assess it. It never invokes command or approval endpoints
and its output does not award live domain or hardware acceptance automatically.
