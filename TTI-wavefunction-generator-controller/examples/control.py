"""Example: python examples/control.py --channel 1 --modulation fm [--enable]."""

import argparse
import json
import urllib.error
import urllib.request


def request(base, path, method="GET", data=None):
    encoded = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(base.rstrip("/") + "/api" + path, data=encoded,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"HTTP {exc.code}: {exc.read().decode()}") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8005")
    parser.add_argument("--channel", type=int, choices=[1, 2], default=1)
    parser.add_argument("--modulation", choices=["off", "am", "fm"], default="off")
    parser.add_argument("--enable", action="store_true", help="Explicitly enable the selected output after applying.")
    args = parser.parse_args()
    state = request(args.url, "/state")
    print(f"Mode: {state['mode']}; connected: {state['connected']}")
    if not state["connected"]:
        raise SystemExit("Connect in the browser first.")
    state = request(args.url, f"/channels/{args.channel}/settings", "PUT", {
        "frequency_hz": 1_000_000, "amplitude": 1, "amplitude_unit": "Vpp", "phase_deg": 0,
        "modulation": {"mode": args.modulation, "frequency_hz": 1000, "depth_percent": 50, "deviation_hz": 10000}})
    if args.enable:
        state = request(args.url, f"/channels/{args.channel}/output", "PUT", {"enabled": True})
    print(json.dumps(state["channels"][args.channel - 1], indent=2))


if __name__ == "__main__":
    main()
