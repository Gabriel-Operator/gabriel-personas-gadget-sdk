"""Send owner-supplied configuration over USB. Never print credentials."""
import argparse
import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", required=True)
    p.add_argument("--ssid", required=True)
    p.add_argument("--password-env", default="GADGET_WIFI_PASSWORD")
    p.add_argument("--token-file", type=Path, required=True)
    p.add_argument("--origin", required=True)
    p.add_argument("--ca-file", type=Path)
    p.add_argument("--persona", default="boli")
    p.add_argument("--backend", choices=("fixture","cloud","local"), default="fixture")
    p.add_argument("--time-server", default="", help="Optional trusted LAN NTP server; no WAN time query is made by default")
    args=p.parse_args()
    if urlsplit(args.origin).scheme!="https": p.error("Firmware requires a trusted HTTPS bridge.")
    token=args.token_file.read_text().strip()
    if not token.startswith("gdev_"): p.error("Use an enrolled device token, not a Persona Token.")
    password=os.environ.get(args.password_env)
    if password is None: p.error("Set the named Wi-Fi password environment variable.")
    payload={"ssid":args.ssid,"password":password,"origin":args.origin.rstrip("/"),"deviceToken":token,
             "caPem":args.ca_file.read_text() if args.ca_file else "", "persona":args.persona,"backend":args.backend,
             "clockEpoch":int(time.time()), "timeServer":args.time_server}
    encoded=(json.dumps(payload,separators=(",",":"))+"\n").encode()
    if len(encoded)>15000: p.error("Provisioning payload exceeds the firmware limit.")
    try:
        import serial
    except ImportError:
        p.error("Install pyserial: python3 -m pip install pyserial==3.5")
    with serial.Serial(args.port,115200,timeout=1) as device:
        time.sleep(2); device.reset_input_buffer(); device.write(encoded); device.flush()
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            line=device.readline()
            if b"GADGET_PROVISIONED" in line:
                print("Device provisioned. Restart it to join Wi-Fi."); return
            if b"GADGET_PROVISION_REJECTED" in line or b"GADGET_PROVISION_FAILED" in line:
                raise SystemExit("Device rejected configuration; credentials were not printed.")
    raise SystemExit("No provisioning acknowledgement. Inspect device status without printing credentials.")


if __name__=="__main__": main()
