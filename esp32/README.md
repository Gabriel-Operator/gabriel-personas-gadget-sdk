# ESP32-S3 device client

Build with **ESP-IDF 6.0.1**. The initial target is an ESP32-S3 DevKitC-1 N8R8
(8 MB flash / 8 MB PSRAM). It uses BOOT/GPIO0 for the example or push-to-talk
button and a USB/UART console for persona selection and complete result output.
The bridge serves all 14 example packages; the firmware also lists their IDs.

No Gabriel owner token, Wi-Fi password or device credential is compiled into the
binary. Configuration is provisioned over USB into encrypted NVS after flashing.
The development profile generates XTS keys in its flash key partition without
burning eFuses. Those keys need reviewed hardware protection before production.
The gadget does not pair with the Muse app or require a Muse SDK token.

## Build

After activating Espressif's ESP-IDF environment:

```sh
cd esp32
idf.py -B build/basic -DIDF_TARGET=esp32s3 -DSDKCONFIG=build/basic/sdkconfig \
  '-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.s3' build
```

Optional external I2S microphone and speaker:

```sh
idf.py -B build/voice -DIDF_TARGET=esp32s3 -DSDKCONFIG=build/voice/sdkconfig \
  '-DSDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.s3;sdkconfig.voice' build
```

The optional example wiring uses an **INMP441 microphone** (left slot, 32-bit
I2S capture converted to mono PCM16) and **MAX98357A I2S amplifier**:

| Signal | GPIO |
| --- | --- |
| Microphone BCLK / WS / DATA | 4 / 5 / 6 |
| Speaker BCLK / WS / DATA | 15 / 16 / 17 |
| Button | 0, active low |

Use the voltage, grounding and speaker requirements in the module vendor's
documentation. These GPIOs are an example for the named development board, not
a universal wiring recipe. The built-in codecs/screens on Waveshare badges or
ESP-BOX boards require a separate board adapter; do not flash this profile as
though it were their validated firmware.

## Flash and provision

Choose your own board's serial port. Flash only a board you control:

```sh
idf.py -B build/basic -p YOUR_SERIAL_PORT flash
python3 -m pip install pyserial==3.5
```

Start an HTTPS bridge with a certificate whose SAN matches its hostname/IP.
Enroll a device on that bridge for the intended persona IDs. Verify the CA
fingerprint through a trusted path and keep the credential file private.

Set `GADGET_WIFI_PASSWORD` through your private environment/secret manager, then:

```sh
python3 esp32/tools/provision.py --port YOUR_SERIAL_PORT --ssid YOUR_WIFI_SSID \
  --origin https://YOUR_BRIDGE_HOST:8765 --ca-file YOUR_TRUSTED_CA_FILE \
  --token-file .state/desk.token --persona boli --backend fixture
```

Restart the board to join Wi-Fi. Provisioning acknowledges success without
printing secrets. A trusted HTTPS origin and device-scoped token are mandatory.
The firmware will not disable TLS verification or accept a Persona Token.

The provisioning tool supplies the host's current clock for certificate checks.
For ongoing operation, use `--time-server YOUR_TRUSTED_LAN_NTP_HOST` or a board
RTC adapter. No WAN time query is made by default. A board without RTC restores
its provisioning-time clock after power loss; refresh time before relying on
certificate expiry checks. Clock trust is a physical acceptance prerequisite.

## Interaction

Press BOOT to run the selected fixture. For connected voice, configure the bridge
binding, enable `stt` (and `tts` for spoken replies), build the voice profile and
select cloud/local. Hold BOOT while speaking and release to send, up to the
configured maximum recording duration. The speaker accepts PCM16 mono WAV at
8–48 kHz. A provider that cannot return that format leaves the text reply available.

Console commands:

```
personas
catalog
persona kai
backend fixture
text Prepare the restock proposal.
recover
reviewed-clear
```

`catalog` shows only enrolled personas. Custom IDs can be selected with `persona ID`.
The bridge enforces the allowlist. The firmware stores a pending operation before
sending; reconnect and reboot do not replay it. `recover` retrieves its receipt.
If a result remains uncertain, inspect the backend outcome before explicitly
acknowledging with `reviewed-clear`; that command never resends the prior turn.

Full proposals and protected live approvals belong on the companion simulator
or authenticated Persona app. The firmware never evaluates chat text as a shell,
GPIO or network command. Board display/codec adapters are extension work.

## Validation boundary

Both build profiles are covered by the CI matrix. Compile/contract results do
not prove microphone wiring, speaker levels, display behavior, battery life,
physical credential protection or real provider quality. Record those checks
against the exact board and installed backend. See docs/validation.md.
