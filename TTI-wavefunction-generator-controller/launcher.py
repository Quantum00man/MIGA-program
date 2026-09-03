"""Cross-platform environment setup and foreground server launcher (standard library only)."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8005
MIN_PYTHON = (3, 10)


class LaunchError(Exception):
    pass


def say(message):
    print(message, flush=True)


def port_number(value):
    try:
        number = int(value)
        if 1 <= number <= 65535:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("port must be between 1 and 65535")


def browser_host(host):
    if host in ("0.0.0.0", "::"):
        return "127.0.0.1" if host == "0.0.0.0" else "[::1]"
    return f"[{host}]" if ":" in host else host


def base_url(host, port):
    return f"http://{browser_host(host)}:{port}"


def server_status(host, port):
    """Use only local HTTP reads; never send instrument commands."""
    connect_host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
    try:
        with socket.create_connection((connect_host, port), timeout=0.5):
            pass
    except OSError as exc:
        # Windows may time out instead of refusing a connection to an unused
        # localhost port. A successful exclusive bind proves local availability.
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            for family, kind, protocol, _, address in addresses:
                with socket.socket(family, kind, protocol) as probe:
                    if os.name == "nt":
                        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    probe.bind(address)
            if addresses:
                return "free"
        except OSError:
            pass
        raise LaunchError(f"Cannot check or bind {host}:{port}: {exc}. Check --host, --port and local firewall rules.") from exc
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(base_url(host, port) + "/openapi.json", timeout=1) as response:
            schema = json.loads(response.read(2_000_000))
        if (isinstance(schema, dict) and isinstance(schema.get("info"), dict)
                and isinstance(schema.get("paths"), dict)
                and schema["info"].get("title") == "TGF3162 Controller"
                and "/api/channels/{channel}/output" in schema["paths"]):
            return "controller"
    except (OSError, ValueError, urllib.error.URLError):
        pass
    return "occupied"


class LauncherLock:
    """An OS lock, automatically released on exit, including abnormal exit."""

    def __enter__(self):
        self.file = (ROOT / ".launcher.lock").open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise LaunchError("Another launcher is setting up or running this project. Use its terminal/browser, or wait for setup to finish.") from exc
        return self

    def __exit__(self, *_):
        self.file.close()


def run(command, context):
    result = subprocess.run([str(arg) for arg in command], cwd=ROOT)
    if result.returncode:
        raise LaunchError(f"{context} failed (exit {result.returncode}). See the command output above.")


def runtime_info(python):
    code = ("import json,sys,fastapi,uvicorn,pydantic; "
            "assert sys.version_info >= (3,10); "
            "assert int(pydantic.__version__.split('.')[0]) == 2; "
            "print(json.dumps({'python':list(sys.version_info[:3]),'prefix':sys.prefix}))")
    try:
        result = subprocess.run([str(python), "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def setup_environment(venv_dir, reinstall=False):
    python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        if venv_dir.exists() and any(venv_dir.iterdir()):
            raise LaunchError(f"The environment at {venv_dir} is incomplete or belongs to another OS. Use --venv with a new directory, or move the old environment aside and retry.")
        say(f"[1/3] Creating Python environment: {venv_dir}")
        try:
            run([sys.executable, "-m", "venv", venv_dir], "Virtual environment creation")
        except LaunchError as exc:
            hint = ("Repair your Python installation (including pip and venv)." if os.name == "nt"
                    else "On Ubuntu, install the matching venv package: sudo apt install python3-venv (or python3.X-venv for a custom Python).")
            raise LaunchError(f"{exc}\n{hint}\nThe partial environment was preserved; use --venv with a new directory on retry.") from exc
    marker = venv_dir / ".tgf-environment.json"
    digest = hashlib.sha256((ROOT / "pyproject.toml").read_bytes() + str(ROOT).encode()).hexdigest()
    info = runtime_info(python)
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        recorded = {}
    if not reinstall and info and recorded == {"digest": digest, "runtime": info}:
        say("[2/3] Environment is ready. Reusing installed dependencies (no download).")
        return python
    say("[2/3] Installing application dependencies. First setup requires internet access.")
    try:
        run([python, "-m", "pip", "install", "--disable-pip-version-check", "-e", ROOT], "Dependency installation")
    except LaunchError as exc:
        raise LaunchError(f"{exc}\nCheck internet/proxy access and retry. For a private package mirror, set PIP_INDEX_URL before launching.") from exc
    info = runtime_info(python)
    if not info:
        raise LaunchError("The installed environment could not import FastAPI, Uvicorn and Pydantic 2. Read the installation output; try --venv with a new directory.")
    # Do not silently use a moved/broken venv which resolves back to the system interpreter.
    if Path(info["prefix"]).resolve() != venv_dir.resolve():
        raise LaunchError("Python did not activate the requested virtual environment. Use --venv with a new directory.")
    marker.write_text(json.dumps({"digest": digest, "runtime": info}, indent=2), encoding="utf-8")
    return python


def open_page(url, disabled):
    say(f"Control panel: {url}")
    if not disabled:
        try:
            if not webbrowser.open(url):
                say("No browser could be opened. Open the address above manually.")
        except webbrowser.Error:
            say("No browser could be opened. Open the address above manually.")


def serve(python, host, port, no_browser):
    say("[3/3] Starting TGF3162 Controller. Keep this terminal open; Ctrl+C stops the server.")
    say("Stopping the server does not switch off hardware outputs.")
    process = subprocess.Popen([str(python), "-m", "uvicorn", "tgf_controller.app:app",
                                "--host", host, "--port", str(port), "--workers", "1"], cwd=ROOT)
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise LaunchError(f"Server exited during startup (exit {process.returncode}). Read the server log above.")
            try:
                ready = server_status(host, port) == "controller"
            except LaunchError:
                ready = False
            if ready:
                open_page(base_url(host, port), no_browser)
                return process.wait()
            time.sleep(0.2)
        raise LaunchError("Server did not become ready within 20 seconds. Read the log above and check the configured address.")
    except KeyboardInterrupt:
        say("\nStopping the controller server...")
        # Console Ctrl+C normally reaches both processes. Allow Uvicorn to close first.
        try:
            process.wait(timeout=3)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            pass
        return 0
    finally:
        if process.poll() is None:
            if os.name == "nt":
                # Windows venv python.exe can be a redirector with a real Python
                # child. Terminating only the redirector leaves Uvicorn running.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set up a local Python environment and start TGF3162 Controller.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server bind address (default: all network interfaces)")
    parser.add_argument("--port", type=port_number, default=DEFAULT_PORT, help="Web server port (not instrument port 9221)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser (useful on headless Ubuntu)")
    parser.add_argument("--setup-only", action="store_true", help="Prepare dependencies without starting a server")
    parser.add_argument("--reinstall", action="store_true", help="Run dependency installation again")
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv", help="Virtual environment directory")
    args = parser.parse_args(argv)
    if sys.version_info < MIN_PYTHON:
        raise LaunchError("Python 3.10 or newer is required. Install a supported Python and retry.")
    # Check existing services before touching the environment or starting another process.
    if not args.setup_only:
        status = server_status(args.host, args.port)
        if status == "controller":
            say("TGF3162 Controller is already running. Reusing it; no settings were changed.")
            open_page(base_url(args.host, args.port), args.no_browser)
            return 0
        if status == "occupied":
            raise LaunchError(f"Port {args.port} is used by another service. Stop that service or specify --port with a free port. No process was stopped.")
    venv_dir = args.venv.expanduser()
    if not venv_dir.is_absolute():
        venv_dir = ROOT / venv_dir
    with LauncherLock():
        python = setup_environment(venv_dir.resolve(), args.reinstall)
        if args.setup_only:
            say("Setup complete. Run the launcher again to start the application.")
            return 0
        return serve(python, args.host, args.port, args.no_browser)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (LaunchError, OSError) as error:
        say(f"\nERROR: {error}")
        sys.exit(1)
    except KeyboardInterrupt:
        say("\nSetup interrupted. Run the launcher again when ready.")
        sys.exit(130)
