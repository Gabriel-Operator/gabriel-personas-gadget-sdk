# Contributing

Use Python 3.10+ and ESP-IDF 6.0.1 for the firmware. The Python runtime has no
third-party dependencies. Follow AGENTS.md and run the documented checks.

Add domain behavior with synthetic fixtures, positive and negative acceptance
cases, and a visible approval boundary. Keep exact source/package parity with
scripts/sync_packs.py. Avoid credentials, private IDs and external runtime state.
Source examples must be runnable without the author's private repositories.

For hardware adapters, document the exact board revision, GPIO wiring, codec,
memory requirements, build profile and actual hardware checks. Keep generic
transport and domain logic separate from board-specific presentation. A build
success is not a pairing, microphone, display, battery or physical-security test.

Pull requests should state resulting behavior, validation evidence and remaining
limitations. Don't label synthetic media, fixture approvals or mock provider
outputs as live task completion, realized ROI or physical-hardware acceptance.
