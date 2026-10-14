# Linux / Raspberry Pi client and bridge

Use Python 3.10+ on a Raspberry Pi 5 or another Linux host. The core SDK needs
no dependencies. Install from the repository into a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/gabriel-gadget doctor --json
```

Use the bridge on the Pi or a nearby computer. Enroll a device and start the
bridge as shown in the root README. Device tokens are saved privately; the device
client never needs a Gabriel owner token. A Pi can connect to Cloud or an existing
LAN GPU appliance. Running the full Portable Runtime on Pi is not validated here.

For a LAN bridge supply `--host 0.0.0.0 --cert YOUR_CERT --key YOUR_KEY`; the
certificate must match the host/IP and its CA must be trusted by clients. A
reverse proxy can also terminate TLS while the bridge remains on loopback.

Example device client:

```sh
gabriel-gadget capabilities kai --bridge https://YOUR_BRIDGE_HOST:8765 \
  --ca YOUR_TRUSTED_CA_FILE --token-file YOUR_DEVICE_TOKEN_FILE --backend local
gabriel-gadget chat kai --bridge https://YOUR_BRIDGE_HOST:8765 \
  --ca YOUR_TRUSTED_CA_FILE --token-file YOUR_DEVICE_TOKEN_FILE --backend local \
  --text 'Prepare a restock proposal from my inventory.'
```

Voice uses ALSA `arecord` and ffmpeg `ffplay`, installed through your OS package
manager. Existing recordings can use `--audio-file`. Camera/phone inputs are
provided through a trusted HTTPS `--image-url`; no camera capture or vision model
is claimed by the fixture engine.

For a persistent bridge, adapt `gabriel-gadget.service.example`. Run under a
dedicated account without sudo access, and keep its environment/state directories
private. Do not expose this owner-device service as a public multi-tenant API.
Credential rotation and revocation are explicit CLI commands.
