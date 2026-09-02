# TGF3162 Controller

A local Python/FastAPI application and English browser interface for the **Aim-TTi TGF3162**. Windows and Ubuntu are supported by the implementation. No Node.js build is needed to run the application.

## Features

- Two independent sine channels: frequency, amplitude, phase and output enable.
- Vpp, Vrms and dBm entry, assuming **50 ohms** and **zero DC offset**.
- Internal sine AM: modulation frequency and depth.
- Internal sine FM: modulation frequency and deviation.
- Configurable instrument IP, TCP port and API-configurable timeout; identity-based connection test.
- Explicit demo mode, command history, server-side limits and serialized instrument transactions.
- Browser UI at `/`, interactive API documentation at `/docs`, schema at `/openapi.json`.

**Hardware validation is pending.** Automated tests exercise the API and a local TCP peer. They cannot verify instrument firmware behavior or physical waveforms.

## Quick start launcher

**Windows:** double-click `start_windows.cmd`. A terminal shows setup progress and remains open while the server runs. Python 3.10+ is required; if missing, the launcher shows an installation command. Failures remain visible in the terminal.

**Ubuntu:** from the project directory, run:

```bash
bash start_ubuntu.sh
```

Or run `chmod +x start_ubuntu.sh` once and use `./start_ubuntu.sh`. If Python or venv is missing, follow the displayed `apt` command, then rerun. The launcher does not change system packages or require administrator access for its own environment.

Both launchers create `.venv`, install the application and its dependencies, start one server worker, then open the browser when the service is ready. First setup needs internet access; subsequent launches reuse the environment without downloading unless `pyproject.toml`, the project location or runtime changes. Dependencies stay inside the virtual environment. An existing controller on the requested port is reused; another service on that port produces an error instead of being stopped.

Common options (pass after either launcher):

```text
--setup-only           Prepare the environment without starting
--no-browser           Start without opening a browser
--port 8001            Select the web port (instrument port stays 9221)
--host 0.0.0.0         Allow clients on the trusted lab network
--reinstall            Run dependency installation again
--venv .venv-ubuntu    Use a separate environment directory
```

For example: `bash start_ubuntu.sh --no-browser --port 8001`, or `start_windows.cmd --setup-only`. Do not copy a Windows virtual environment to Ubuntu: omit `.venv` when transferring the project, or select a fresh environment with `--venv`.

Set `TGF_PYTHON` to a specific Python executable if automatic discovery selects the wrong installation. Advanced users can run `python launcher.py` directly. `TGF_NO_PAUSE=1` disables the Windows error pause for unattended scripts. Use Ctrl+C in the launcher terminal to stop the server. Stopping the launcher never switches off hardware outputs.

Launcher validation: the Windows entry point, fresh environment installation, cached setup, real server startup and child-process cleanup were exercised locally. Ten launcher tests cover service reuse, occupied ports, environment preservation, install caching and setup locks. The Ubuntu shell entry passed Bash syntax validation; actual Ubuntu execution remains to be verified. These tests are included in the existing Windows/Ubuntu CI matrix.

## Manual install and run

Requires Python 3.10 or newer. Run commands from this directory.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m uvicorn tgf_controller.app:app --host 127.0.0.1 --port 8000
```

Ubuntu:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m uvicorn tgf_controller.app:app --host 127.0.0.1 --port 8000
```

If Ubuntu reports that `venv` is unavailable, install `python3-venv` using your system package manager. Then open **http://127.0.0.1:8000**. The first launch starts in **Demo Mode** with both simulated outputs off. Subsequent launches load connection preferences; saved LAN sessions remain disconnected until explicitly connected.

Use **one Uvicorn worker and one application instance per instrument**. The connection and channel-selection lock are process-local. Multiple workers or separate programs controlling the same instrument can invalidate channel state and interleave commands.

The control page is self-contained and works without internet access after installation. FastAPI's default interactive `/docs` viewer loads Swagger UI assets from a CDN; the JSON schema at `/openapi.json` and Python API work offline.

The default bind address exposes the app only on its host computer. If another computer must use it, `--host 0.0.0.0` exposes it to the local network. This version has no user authentication and is intended for a trusted lab network, not the public internet.

## Browser workflow

1. Try Demo Mode first. Edit a channel and press **Apply**.
2. Switch that channel's output **On** or **Off** independently. On is unavailable until settings are known and pending edits have been applied. Off remains available even if the initial hardware state is unknown.
3. Choose **LAN instrument**, enter the IP and port **9221**, and use **Test Connection**. The test sends `*IDN?` and checks for model `TGF3162`; it is more useful than a ping alone.
4. Use **Save & Connect**. If switching sessions, the previous connection is closed first. Hardware outputs are unchanged by disconnecting.
5. Apply each channel's configuration, then explicitly enable the required outputs.

Changing a unit preserves its physical value: for example, changing 10 kHz to MHz displays 0.01 MHz. Editing alone never writes to the instrument. **Apply changes a running waveform without turning its output off**, and uses several sequential commands; it is not glitch-free or atomic. If a parameter transition must not appear at the load, turn that output off first, apply, then turn it on.

**Closing the browser, stopping the server or disconnecting does not switch off hardware outputs.** Use the individual Off controls when that is required. Connection failures do not trigger automatic retries of writes or automatic output restoration.

## State and readback

The published TGF3000 remote command table documents `FREQ`, `AMPL`, `PHASE`, `MOD...` and `OUTPUT` setters, but not corresponding individual queries. `*LRN?` produces an opaque binary setup block; its internal format is not documented and is not decoded here.

For that reason:

- A new LAN connection starts with **unknown** channel settings and output state.
- Applying a configuration records the commands after checking `EER?`, `QER?`, `*ESR?` and `*OPC?`. `source: "commanded"` means **accepted commands**, not measured output or parameter readback. Instrument rounding may differ from the submitted amplitude.
- Demo state has `source: "simulation"`. It is never hardware evidence.
- **Check connection** verifies identity and status registers. It cannot observe front-panel edits or an actual analog output.
- If someone changes settings locally or from another application, reapply the desired channel configuration before enabling output. Use one controller at a time.
- Partial command failures or link loss invalidate the cached channel state and close the session. Some commands may already have taken effect. Reconnect, inspect the instrument and reapply; there is no rollback claim.
- Status-register reads clear those registers. Prior errors encountered before an operation are retained in Activity.

## Parameter limits and units

| Parameter | Limit |
| --- | --- |
| Sine carrier | 1 µHz to 160 MHz; 1 µHz resolution |
| Amplitude, up to 50 MHz | 0.01 to 10 Vpp into 50 ohms |
| Amplitude, above 50 to 100 MHz | 0.01 to 5 Vpp |
| Amplitude, above 100 to 160 MHz | 0.01 to 2.5 Vpp |
| Phase | -360 to +360 degrees; 0.001 degree resolution |
| AM carrier | Up to 50 MHz |
| AM/FM internal modulation frequency | 1 µHz to 10 MHz; 1 µHz resolution |
| AM depth | 0 to 100%; 0.01% resolution |
| FM deviation | At most min(carrier, 160 MHz - carrier, 80 MHz) |

The manual states FM deviation is limited to `Fmax/2`. The implementation additionally keeps the instantaneous frequency range within 0–160 MHz and conservatively uses its upper edge to choose the amplitude limit. This combined-range policy needs confirmation on hardware.

The native amplitude command accepts **Vpp only**. Other entries use unmodulated sine equivalents:

```text
Vpp = 2 × sqrt(2) × Vrms
Power in watts = Vrms² / 50
dBm = 10 × log10(Power / 0.001)
```

For AM these are equivalent levels of the programmed Vpp setting, **not measured total RMS or average RF power of the modulated waveform**. AM envelope behavior at large amplitude/depth must be verified on hardware. The manual lists amplitude resolution as 3 digits or 1 mV; the application does not invent a more precise readback.

Each phase is an offset relative to the instrument's reference. Two different carrier frequencies do not have a constant relative phase. No `ALIGN`, synchronized start or external clock configuration is sent.

## Python API example

Install `httpx` in your script's environment. This example works against the initial Demo Mode session. The same channel endpoints control hardware after LAN connection.

```python
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=120) as api:
    response = api.put("/api/channels/1/settings", json={
        "frequency_hz": 1_000_000,
        "amplitude": 1.0,
        "amplitude_unit": "Vpp",
        "phase_deg": 30,
        "modulation": {
            "mode": "am",
            "frequency_hz": 1000,
            "depth_percent": 40,
        },
    })
    response.raise_for_status()
    print(response.json()["channels"][0])

    # This explicitly enables CH1. CH2 is unchanged.
    response = api.put("/api/channels/1/output", json={"enabled": True})
    response.raise_for_status()
```

To configure LAN, call `POST /api/disconnect`, then `PUT /api/connection` with `{"mode":"lan","host":"192.168.1.100","port":9221,"timeout_s":3}`, then `POST /api/connect`. Use your instrument's actual IP. The connection endpoint changes the application's target, not the instrument's network settings. A complete runnable script is in `examples/control.py`; output enable requires its explicit `--enable` flag.

API operations:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/state` | Local state and activity, no hardware query |
| PUT | `/api/connection` | Save connection configuration while disconnected |
| POST | `/api/connection/test` | Test supplied settings without saving |
| POST | `/api/connect` | Connect to saved target |
| POST | `/api/disconnect` | Close session, leave outputs unchanged |
| POST | `/api/refresh` | Query identity and error status |
| PUT | `/api/channels/{1 or 2}/settings` | Apply full sine configuration |
| PUT | `/api/channels/{1 or 2}/output` | Explicit output On/Off |

`settings` is a complete configuration, not a patch; omitted fields take documented model defaults. Error status 422 indicates invalid parameters, 409 a state/model conflict, 502 a device rejection and 503 a connection failure.

## Configuration files

Windows: `%APPDATA%/tgf3162-controller/connection.json`.

Ubuntu: `~/.config/tgf3162-controller/connection.json`.

Set `TGF_CONFIG_PATH` to use a different file. Preferences contain only connection settings; output enable and channel configurations are never restored from disk.

## Verification

```bash
python -m pip install -e ".[test]"
python -m pytest -q
```

The tests cover API validation, conversions, independent outputs, config persistence, real TCP framing against a test peer, wrong model rejection, partial failures, power-cycle invalidation and transaction serialization. A GitHub Actions matrix is provided for Windows and Ubuntu; those remote CI jobs have not been run in this development session. See `docs/hardware-validation.md` before first hardware use and `docs/design-review.md` for interface review evidence.

## Protocol reference

Primary source: [Aim-TTi TGF3000 instruction manual, Issue 5 download](https://resources.aimtti.com/manuals/TGF3000_Series_Instruction_Manual-Iss5.pdf), sections 3, 7, 11, 22.4, 22.6 and 23.3. The text inside this download identifies itself as Issue 4; record the actual firmware and manual revision during hardware verification.

See `docs/protocol.md` for the exact command sequence and limitations. This software targets TGF3162 specifically, not TGF3082 or the newer TGF4000 family.
