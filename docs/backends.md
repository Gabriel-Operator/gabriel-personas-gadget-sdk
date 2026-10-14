# Cloud and private LAN backends

The device always talks to the bridge. `backend: fixture|cloud|local` selects a
configured execution profile, and a device must be enrolled for the selected
persona. Profiles do not fall back to one another.

## Gabriel Cloud

1. Create/configure and publish your persona using Gabriel Operator's authoring
   UI or the documented Gateway lifecycle. Existing published personas can be used.
2. Mint a Persona Token from **Chat Publish → SDK / API Integration**. A workspace
   Gateway token can provision/mint, but it must not be used as the gadget's runtime token.
3. Add the published persona ID to the chosen binding in `backends.json`. Do not
   copy IDs from the synthetic packages; they are authored portable resource keys.
4. Supply the token through the named environment variable using your usual secret
   manager or a private environment file. Do not paste tokens into coding-agent chat.
5. Start the bridge with `--config backends.json`, then inspect capabilities before
   using audio, image input or commands.

`GET /api/v1/models` must return the expected `gabriel/<published-persona-id>`.
The bridge refuses a token bound to another persona. Each binding needs its own
persona token. The example configuration contains bindings for Boli, KAI and
Chakri; add the same shape for the remaining examples or custom packages.

The sample chat-configs deliberately use explanation-only `assistant_reply`
commands. Existing production personas have their own operators and governance;
connecting one does not replace it with the fixture engine.

## Local Portable Runtime appliance

Provision the appliance using Gabriel's existing signed installer, activation,
pairing and immutable published-candidate deployment flow. This SDK does not
remove that trust/lease contract or redistribute the runtime image.

Configure `profiles.local.origin` as the appliance's private HTTPS origin, supply
its trusted CA file, and use a persona-scoped credential valid on that appliance.
When the paired appliance requires mTLS, also set `clientCertFile` and
`clientKeyFile` to the privately saved client certificate/key issued through its
supported pairing flow. The bridge loads that chain without exposing it to devices.
Pairing/device-management credentials alone are not automatically a Persona Token.
Create the runtime binding using the appliance's supported authoring/credential
flow and verify `/api/v1/models` before a gadget call. Core API compatibility must
be established against the installed appliance version.

```json
{
  "origin": "https://192.168.1.10:8443",
  "caFile": "/path/to/trusted-appliance-ca.pem",
  "clientCertFile": "/path/to/paired-client-cert.pem",
  "clientKeyFile": "/path/to/paired-client-key.pem",
  "bindings": {
    "boli": {"personaId": "YOUR_PUBLISHED_PERSONA_ID", "tokenEnv": "GABRIEL_LOCAL_BOLI_TOKEN"}
  }
}
```

Keep WAN/DNS disconnected during actual local acceptance. Local mode does not
silently route speech or tools through cloud. A missing installed local speech,
vision or tool adapter remains unavailable. The current Gabriel appliance targets
DGX Spark / compatible RTX Linux; this SDK's Pi client support does not establish
full appliance inference support on Pi.

Loopback development API servers may use HTTP only with `allowLoopbackHttp: true`.
Public origins are rejected in local mode. TLS verification cannot be disabled.

## Chat, commands and audio

Chat session IDs are retained by `(device, persona, backend)` and forwarded in
`metadata.session_id`. Commands must be declared by the package and returned by
the published `/commands` endpoint. Complex command intake may return
`requires_input`; finish it in the authenticated Persona app rather than guessing.

For Linux voice, install ALSA utilities and ffmpeg, then:

```sh
gabriel-gadget voice boli --backend cloud --seconds 4 \
  --token-file .state/desk.token --loopback-dev --output reply.mp3 --play
```

`--audio-file sample.wav` accepts an existing recording. The bridge requires `stt`
for transcription and `tts` for speech output. Browser voice being enabled does
not by itself prove those Persona API capabilities are configured. Firmware
requests PCM WAV replies for its I2S speaker; providers returning another format
leave the completed text reply available with `speechError`.

Rate limits are returned without replaying a POST. After an uncertain request,
retrieve its receipt and reconcile any backend job before creating a new turn.
TTS failure preserves the completed text response to avoid repeating persona work.

Protected live approval stays in the authenticated Persona app. The bridge's
`/v1/reviews` endpoint accepts only synthetic fixture receipts.

References: [Gabriel gateway docs](https://gabrieloperator.com/docs/gateway),
[Portable Runtime skill](https://github.com/Gabriel-Operator/portable-persona-runtime).
