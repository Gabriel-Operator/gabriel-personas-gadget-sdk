# Security and private state

Report vulnerabilities privately to hello@gabrieloperator.com. Do not publish
tokens or real user data in GitHub issues. Include reproducible synthetic input.

Backend tokens remain in the bridge environment. Device credentials are random,
hashed at rest, revocable, and limited to enrolled persona IDs. Private SQLite
state uses a 0700 directory and 0600 database. Browser credentials stay in memory,
not localStorage or URLs. API logs omit prompts, bearer headers and response data.

The bridge refuses insecure LAN serving and verifies backend TLS using system or
owner-supplied CA trust. Local execution origins must resolve to private/loopback
addresses; they do not fall back to cloud. Firmware requires HTTPS and an owner
provisioned trust chain. Never put owner/workspace tokens into firmware.

This release is for owner-controlled devices and bindings. A device ID or chat
user label is not proof of another person's identity. Shared-device identity,
delegated subscriber grants, hardware-backed attestation and fleet management
are separate work. Run the bridge on a trusted private network with OS access
controls; its stdlib HTTP server is not a public multi-tenant hosting service.

Receipts prevent an SDK reconnect from automatically repeating a POST. They
cannot guarantee atomicity in external systems. Uncertain operations require
reconciliation. A synthetic review receipt never authorizes live side effects.

The development firmware encrypts NVS data using generated XTS keys stored in its
flash key partition and never burns eFuses automatically. Without reviewed
secure boot/flash-encryption provisioning, extracting both data and keys defeats
that protection. Production provisioning must verify those controls,
clock trust, signed firmware/OTA and board-specific recovery. No boards are flashed
by repository tests, and no physical security acceptance is claimed.
