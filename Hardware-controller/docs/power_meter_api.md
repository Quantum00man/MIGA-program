# PM100A LAN API

The Windows controller serves a fresh PM100A measurement at `GET /api/power-meter`.
The service listens on port `8050` on the Windows host. Use the Windows IP address
reachable from the Linux computer; the two computers must be on a network that
permits TCP connections to that port.

Check reachability from Linux before logging in:

```bash
curl http://WINDOWS_IP:8050/health
```

A response with `"status":"ok"` confirms that the HTTP service is reachable.
Choose the Windows IP address on the network shared with Linux. If this check
cannot connect, verify the address, routing, and Windows inbound firewall rule
for TCP port `8050`.

## Authentication

The endpoint uses the same password and session cookie as the browser. Log in with
`POST /auth/login` and retain the returned cookie. The session expires after 12 hours
of inactivity; log in again if a query returns HTTP 401. Use the current web password
and keep it out of source control. The service uses plain HTTP, so use it on a trusted
lab network or through a protected tunnel.

```bash
BASE=http://WINDOWS_IP:8050
curl -c cookies.txt -H 'Content-Type: application/json' \
  -d '{"password":"YOUR_WEB_PASSWORD"}' "$BASE/auth/login"
curl -b cookies.txt "$BASE/api/power-meter"
```

Successful response:

```json
{
  "status": "success",
  "message": "Power meter reading loaded.",
  "data": {
    "power_w": 1.23e-6,
    "wavelength_nm": 780.0,
    "serial_number": "P1002033",
    "measured_at": "2026-09-23T12:34:56.789Z"
  }
}
```

`power_w` is the instantaneous reading in watts. `measured_at` is the Windows
server's UTC time immediately after measurement. The API does not change the
meter's wavelength or other settings. Each request measures the instrument; there
is no cached value. HTTP 502 indicates the meter could not be read, such as when
it is disconnected or occupied by another program. The response has
`Cache-Control: no-store`.

For logged samples, use `data.measured_at` rather than the Linux receive time as
the measurement timestamp. An unsuccessful request is not a valid data point.

## Python client and CSV recorder

The standard-library-only example at `examples/read_power_meter_linux.py` can be
copied to Linux and imported into another program:

```python
from read_power_meter_linux import PowerMeterClient

client = PowerMeterClient("http://WINDOWS_IP:8050", password="YOUR_WEB_PASSWORD")
reading = client.read()
print(reading["power_w"], reading["measured_at"])
```

It logs in automatically and repeats the login if the session expires. To record
one reading per second as CSV:

```bash
export MIGA_CONTROLLER_PASSWORD='YOUR_WEB_PASSWORD'
python3 read_power_meter_linux.py --url http://WINDOWS_IP:8050 --csv power.csv
```

`Ctrl+C` stops the recorder. Failed reads are reported on stderr and skipped; the
next interval is still queried.
