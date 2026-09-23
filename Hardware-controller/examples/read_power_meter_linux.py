"""Read and optionally record PM100A measurements from the controller over HTTP.

Set MIGA_CONTROLLER_PASSWORD and run, for example:
    python3 read_power_meter_linux.py --url http://WINDOWS_IP:8050 --csv power.csv

Other Python programs can import PowerMeterClient and call client.read().
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class PowerMeterClient:
    def __init__(self, base_url: str, password: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def _request(self, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        with self.opener.open(request, timeout=self.timeout) as response:
            return json.load(response)

    def login(self) -> None:
        self._request("/auth/login", {"password": self.password})

    def read(self) -> dict:
        try:
            return self._request("/api/power-meter")["data"]
        except HTTPError as exc:
            if exc.code != 401:
                raise
            self.login()
            return self._request("/api/power-meter")["data"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Record the PM100A power from the MIGA controller.")
    parser.add_argument("--url", required=True, help="Windows controller URL, e.g. http://192.168.1.10:8050")
    parser.add_argument("--csv", type=Path, help="CSV output path; omit to print readings only")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between queries (default: 1)")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    password = os.environ.get("MIGA_CONTROLLER_PASSWORD")
    if not password:
        parser.error("set MIGA_CONTROLLER_PASSWORD to the web login password")

    client = PowerMeterClient(args.url, password)
    client.login()
    fields = ("measured_at", "power_w", "wavelength_nm", "serial_number")
    output = args.csv.open("a", newline="", encoding="utf-8") if args.csv else None
    try:
        writer = csv.DictWriter(output, fieldnames=fields) if output else None
        if writer and output.tell() == 0:
            writer.writeheader()
        while True:
            try:
                reading = client.read()
                print(f"{reading['measured_at']}  {reading['power_w']:.9g} W  ({reading['wavelength_nm']:g} nm)", flush=True)
                if writer:
                    writer.writerow({field: reading[field] for field in fields})
                    output.flush()
            except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
                print(f"Power reading failed: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    main()
