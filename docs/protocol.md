# Device protocol v1

LAN requests require HTTPS and `Authorization: Bearer <device-token>`.
Device tokens begin `gdev_` and are issued by the bridge CLI, not the Gabriel
Gateway. Backend Persona Tokens never appear in a device response.

| Endpoint | Result |
| --- | --- |
| `GET /health` | Public bridge liveness and protocol version |
| `GET /v1/catalog` | Only the personas allowed for this device |
| `GET /v1/capabilities?persona=boli&backend=fixture` | Fixture or actual published capabilities |
| `POST /v1/turns` | Domain fixture, chat, explicit command or batch voice turn |
| `GET /v1/turns/{operationId}` | Device-owned durable receipt for recovery |
| `POST /v1/reviews` | Synthetic review only; never approves live effects |

```json
{
  "persona": "kai",
  "backend": "fixture",
  "operationId": "a-client-generated-stable-id",
  "text": "Prepare a restock proposal."
}
```

Turn options: `facts` overrides a synthetic fixture; `command` explicitly invokes
a declared/published trigger; `imageUrl` provides a bounded HTTPS chat image;
`audioBase64` and `audioMime` provide a recorded voice note; `speak` requests reply
audio; `audioFormat` selects `mp3` or `wav`. Commands use text intake; they are
not selected implicitly from voice. Image handling remains a backend capability.

The maximum JSON request is 3 MiB, audio 2 MiB, and text 16,384 characters.
Operation IDs use 8–96 letters, digits, `_` or `-`. Content must contain finite
numbers. Chunked request bodies are not accepted. Firmware responses are bounded
to 2 MiB; longer media belongs on a companion device.

Completed requests are returned unchanged for the same device, operation ID and
exact payload. Changed payloads get `409 operation_conflict`. Running/interrupted
requests get `409 operation_uncertain` and are not automatically replayed. These
receipts prevent SDK retries from duplicating a request; they do not make an
external provider transactional. Reconcile uncertain backend effects separately.

Receipts report `running`, `done` or `uncertain`; a `done` receipt contains `result`.
Requests and receipts are partitioned by authenticated device. Sessions are also
partitioned by persona and backend. A fixture result contains a revision hash of
the complete prepared proposal. Reviews require that revision:

```json
{
  "operationId": "a-client-generated-stable-id",
  "revision": "THE_CURRENT_RESULT_REVISION",
  "decision": "approve"
}
```

The result is `simulated_approval` or `declined`, with `externalEffects: []`.
Changed or conflicting decisions are rejected. Live receipts return
`403 live_review_required` from this endpoint.

Errors use `{ "error": { "code": "...", "message": "..." } }`. Common codes:
`device_unauthorized`, `persona_forbidden`, `backend_not_configured`,
`persona_binding_mismatch`, `capability_disabled`, `command_unavailable`,
`operation_conflict`, `operation_uncertain`, `review_revision_changed`,
`rate_limited`, and `backend_unreachable`. Provider bodies and credentials are
not included in public error messages.
