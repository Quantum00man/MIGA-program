from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
import winreg


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LAUNCHER_CONFIG_PATH = DATA_DIR / "launcher_config.json"
SERVER_STATE_PATH = DATA_DIR / "launcher_server_state.json"
LOG_PATH = DATA_DIR / "hardware_controller_server.log"
DEFAULT_PORT = 8050
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "MIGA Hardware Controller"


def load_launcher_config() -> dict:
    defaults = {"port": DEFAULT_PORT, "autostart": False, "reload": False}
    try:
        with LAUNCHER_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return defaults
    if not isinstance(raw, dict):
        return defaults
    try:
        port = int(raw.get("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    if not 1 <= port <= 65535:
        port = DEFAULT_PORT
    return {
        "port": port,
        "autostart": bool(raw.get("autostart", False)),
        "reload": bool(raw.get("reload", False)),
    }


def save_launcher_config(port: int, autostart: bool, reload_enabled: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LAUNCHER_CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "port": port,
                "autostart": autostart,
                "reload": reload_enabled,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )


def save_server_state(process_id: int, port: int, reload_enabled: bool) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SERVER_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(
            {"pid": process_id, "port": port, "reload": reload_enabled},
            handle,
            ensure_ascii=False,
            indent=2,
        )


def load_server_state() -> dict | None:
    try:
        with SERVER_STATE_PATH.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
        return {
            "pid": int(state["pid"]),
            "port": int(state["port"]),
            "reload": bool(state.get("reload", False)),
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None


def process_is_running(process_id: int) -> bool:
    if process_id <= 0:
        return False
    try:
        os.kill(process_id, 0)
        return True
    except OSError:
        return False


def listening_process_ids(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pattern = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$", re.IGNORECASE)
    process_ids = []
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            process_id = int(match.group(1))
            if process_id not in process_ids:
                process_ids.append(process_id)
    return process_ids


def running_server_info(port: int) -> dict:
    running = is_miga_server(port)
    state = load_server_state()
    state_matches = bool(
        running
        and state
        and state["port"] == port
        and process_is_running(state["pid"])
    )
    return {
        "running": running,
        "reload": state["reload"] if state_matches else None,
        "pid": state["pid"] if state_matches else None,
    }


def stop_server_process(port: int, timeout_sec: float = 12.0) -> bool:
    if not is_miga_server(port):
        SERVER_STATE_PATH.unlink(missing_ok=True)
        return True

    info = running_server_info(port)
    process_ids = [info["pid"]] if info["pid"] else listening_process_ids(port)
    if not process_ids:
        raise OSError(f"Could not identify the MIGA server process listening on port {port}.")

    for process_id in process_ids:
        result = subprocess.run(
            ["taskkill", "/PID", str(process_id), "/T", "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=8,
            check=False,
        )
        if result.returncode != 0 and process_is_running(process_id):
            raise OSError(result.stderr.strip() or result.stdout.strip() or "Unable to stop the server process.")

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if port_is_available(port):
            SERVER_STATE_PATH.unlink(missing_ok=True)
            return True
        time.sleep(0.25)
    raise OSError(f"The server did not release port {port} within {timeout_sec:g} seconds.")


def python_executable() -> Path:
    preferred = BASE_DIR / ".venv" / "Scripts" / "python.exe"
    return preferred if preferred.exists() else Path(sys.executable)


def pythonw_executable() -> Path:
    preferred = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
    if preferred.exists():
        return preferred
    current = Path(sys.executable)
    candidate = current.with_name("pythonw.exe")
    return candidate if candidate.exists() else current


def set_windows_autostart(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
        if enabled:
            command = subprocess.list2cmdline(
                [str(pythonw_executable()), str(Path(__file__).resolve()), "--autostart"]
            )
            winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass


def is_miga_server(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health",
            timeout=1.0,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("title") == "MIGA Hardware Controller"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def port_is_available(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def launch_server_process(port: int, reload_enabled: bool = False) -> subprocess.Popen:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_PATH.open("a", encoding="utf-8")
    command = [
        str(python_executable()),
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
    ]
    if reload_enabled:
        command.append("--reload")
    try:
        process = subprocess.Popen(
            command,
            cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    finally:
        log_handle.close()
    save_server_state(process.pid, port, reload_enabled)
    return process


def wait_for_server(port: int, process: subprocess.Popen, timeout_sec: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if process.poll() is not None:
            SERVER_STATE_PATH.unlink(missing_ok=True)
            return False
        if is_miga_server(port):
            return True
        time.sleep(0.25)
    return False


def autostart_server() -> int:
    config = load_launcher_config()
    port = config["port"]
    if is_miga_server(port):
        return 0
    if port != DEFAULT_PORT and is_miga_server(DEFAULT_PORT):
        return 0
    if not port_is_available(port):
        return 1
    process = launch_server_process(port, config["reload"])
    return 0 if wait_for_server(port, process) else 1


class LauncherWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("MIGA Hardware Controller Launcher")
        self.root.resizable(False, False)
        self.root.configure(background="#eef3f7")
        self.config = load_launcher_config()
        self.port_var = tk.StringVar(value=str(self.config["port"]))
        self.autostart_var = tk.BooleanVar(value=self.config["autostart"])
        self.reload_var = tk.BooleanVar(value=self.config["reload"])
        self.status_var = tk.StringVar(value="Enter a local port, then start the server.")
        self.mode_var = tk.StringVar(value="Server status: checking...")
        self.start_button: ttk.Button | None = None
        self.stop_button: ttk.Button | None = None
        self.restart_button: ttk.Button | None = None
        self._build()
        self.root.after(100, self._center)
        self.root.after(150, self._refresh_server_status)

    def _build(self):
        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Note.TLabel", foreground="#607489")

        frame = ttk.Frame(self.root, padding=24)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="MIGA Hardware Controller", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            frame,
            text="Choose the local port for the web service.",
            style="Note.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 20))

        ttk.Label(frame, text="Local port").grid(row=2, column=0, sticky="w", padx=(0, 16))
        port_entry = ttk.Entry(frame, textvariable=self.port_var, width=18)
        port_entry.grid(row=2, column=1, sticky="ew")
        port_entry.focus_set()

        ttk.Checkbutton(
            frame,
            text="Start the server automatically after Windows sign-in",
            variable=self.autostart_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(18, 8))

        ttk.Checkbutton(
            frame,
            text="Enable auto-reload when project files change",
            variable=self.reload_var,
            command=self._reload_setting_changed,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Label(
            frame,
            text="The server continues running in the background after this launcher closes.",
            style="Note.TLabel",
        ).grid(row=5, column=0, columnspan=2, sticky="w")

        ttk.Separator(frame).grid(row=6, column=0, columnspan=2, sticky="ew", pady=18)
        ttk.Label(
            frame,
            textvariable=self.status_var,
            wraplength=390,
        ).grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            textvariable=self.mode_var,
            style="Note.TLabel",
            wraplength=390,
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 0))

        button_row = ttk.Frame(frame)
        button_row.grid(row=9, column=0, columnspan=2, sticky="e", pady=(20, 0))
        ttk.Button(button_row, text="Cancel", command=self.root.destroy).grid(row=0, column=0, padx=(0, 10))
        self.stop_button = ttk.Button(button_row, text="Stop Server", command=self.stop)
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        self.restart_button = ttk.Button(button_row, text="Restart Server", command=self.restart)
        self.restart_button.grid(row=0, column=2, padx=(0, 10))
        self.start_button = ttk.Button(button_row, text="Confirm and Start", command=self.start)
        self.start_button.grid(row=0, column=3)

        self.root.bind("<Return>", lambda _event: self.start())

    def _center(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"+{x}+{y}")

    def _validated_port(self) -> int | None:
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Port", "The port must be an integer between 1 and 65535.")
            return None
        if not 1 <= port <= 65535:
            messagebox.showerror("Invalid Port", "The port must be an integer between 1 and 65535.")
            return None
        return port

    def _refresh_server_status(self):
        port = self._validated_port_silent()
        if port is None:
            self.mode_var.set("Server status: invalid port")
            return
        info = running_server_info(port)
        if not info["running"]:
            self.mode_var.set("Server: stopped · Auto-reload: not active")
        elif info["reload"] is True:
            self.mode_var.set("Server: running · Auto-reload: enabled")
        elif info["reload"] is False:
            self.mode_var.set("Server: running · Auto-reload: disabled")
        else:
            self.mode_var.set("Server: running · Auto-reload: unknown (restart to apply)")
        if self.stop_button:
            self.stop_button.configure(state="normal" if info["running"] else "disabled")
        if self.restart_button:
            self.restart_button.configure(state="normal" if info["running"] else "disabled")

    def _validated_port_silent(self) -> int | None:
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            return None
        return port if 1 <= port <= 65535 else None

    def _set_buttons_busy(self, busy: bool):
        state = "disabled" if busy else "normal"
        for button in (self.start_button, self.stop_button, self.restart_button):
            if button:
                button.configure(state=state)

    def _save_settings(self, port: int) -> bool:
        try:
            save_launcher_config(port, self.autostart_var.get(), self.reload_var.get())
            set_windows_autostart(self.autostart_var.get())
            self.config = {
                "port": port,
                "autostart": self.autostart_var.get(),
                "reload": self.reload_var.get(),
            }
            return True
        except OSError as exc:
            messagebox.showerror("Unable to Save Launch Settings", str(exc))
            return False

    def _reload_setting_changed(self):
        port = self._validated_port()
        if port is None or not self._save_settings(port):
            return
        if is_miga_server(port):
            self.status_var.set("Auto-reload setting changed. Restarting the server...")
            self._set_buttons_busy(True)
            threading.Thread(
                target=self._restart_and_report,
                args=(port, self.reload_var.get(), False),
                daemon=True,
            ).start()
        else:
            self.status_var.set("Auto-reload setting saved. It will apply when the server starts.")
            self._refresh_server_status()

    def stop(self):
        port = self._validated_port()
        if port is None:
            return
        if not is_miga_server(port):
            self.status_var.set(f"No MIGA server is running on port {port}.")
            self._refresh_server_status()
            return
        self._set_buttons_busy(True)
        self.status_var.set(f"Stopping the server on port {port}...")
        threading.Thread(target=self._stop_and_report, args=(port,), daemon=True).start()

    def restart(self):
        port = self._validated_port()
        if port is None or not self._save_settings(port):
            return
        self._set_buttons_busy(True)
        self.status_var.set(f"Restarting the server on port {port}...")
        threading.Thread(
            target=self._restart_and_report,
            args=(port, self.reload_var.get(), True),
            daemon=True,
        ).start()

    def start(self):
        port = self._validated_port()
        if port is None:
            return

        existing_ports = {DEFAULT_PORT, int(self.config["port"])}
        for existing_port in existing_ports:
            if existing_port != port and is_miga_server(existing_port):
                messagebox.showinfo(
                    "Server Already Running",
                    f"MIGA Hardware Controller is already running on port {existing_port}. "
                    "Stop the existing server before changing the port.",
                )
                webbrowser.open(f"http://127.0.0.1:{existing_port}")
                return

        if not self._save_settings(port):
            return

        if is_miga_server(port):
            info = running_server_info(port)
            if info["reload"] != self.reload_var.get():
                self.restart()
            else:
                self.status_var.set(f"The server is already running on port {port}. Opening the browser.")
                webbrowser.open(f"http://127.0.0.1:{port}")
            return

        if not port_is_available(port):
            messagebox.showerror(
                "Port Already in Use",
                f"Port {port} is being used by another program. Choose a different port.",
            )
            return

        assert self.start_button is not None
        self.start_button.configure(state="disabled")
        self.status_var.set(f"Starting the server on port {port}...")
        threading.Thread(
            target=self._launch_and_report,
            args=(port, self.reload_var.get()),
            daemon=True,
        ).start()

    def _launch_and_report(self, port: int, reload_enabled: bool):
        try:
            process = launch_server_process(port, reload_enabled)
            success = wait_for_server(port, process)
        except OSError as exc:
            self.root.after(0, self._show_failure, str(exc))
            return
        if success:
            self.root.after(0, self._show_success, port)
        else:
            self.root.after(
                0,
                self._show_failure,
                f"The server did not start successfully. Check the log: {LOG_PATH}",
            )

    def _stop_and_report(self, port: int):
        try:
            stop_server_process(port)
        except OSError as exc:
            self.root.after(0, self._show_failure, str(exc))
            return
        self.root.after(0, self._show_stopped, port)

    def _restart_and_report(self, port: int, reload_enabled: bool, open_browser: bool):
        try:
            stop_server_process(port)
            process = launch_server_process(port, reload_enabled)
            success = wait_for_server(port, process)
        except OSError as exc:
            self.root.after(0, self._show_failure, str(exc))
            return
        if success:
            self.root.after(0, self._show_success, port, open_browser)
        else:
            self.root.after(
                0,
                self._show_failure,
                f"The server did not restart successfully. Check the log: {LOG_PATH}",
            )

    def _show_success(self, port: int, open_browser: bool = True):
        self.status_var.set(f"Server started: http://127.0.0.1:{port}")
        self._set_buttons_busy(False)
        self._refresh_server_status()
        if open_browser:
            webbrowser.open(f"http://127.0.0.1:{port}")

    def _show_stopped(self, port: int):
        self.status_var.set(f"Server stopped on port {port}.")
        self._set_buttons_busy(False)
        self._refresh_server_status()

    def _show_failure(self, message: str):
        self.status_var.set(message)
        self._set_buttons_busy(False)
        self._refresh_server_status()
        messagebox.showerror("Startup Failed", message)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    if "--autostart" in sys.argv:
        raise SystemExit(autostart_server())
    LauncherWindow().run()
