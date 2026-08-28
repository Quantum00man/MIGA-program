"""Minimal English controller for a Keopsys CEFA B202 EDFA."""
from __future__ import annotations

import math
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import serial
from serial.tools import list_ports

BAUDRATE = 19200
MAX_OUTPUT_DBM = 33.0


def parse_answer(answer: str) -> str:
    text = answer.strip().replace("\r", "").replace("\n", "")
    if not text:
        raise TimeoutError("No response from the EDFA")
    if text.endswith("/"):
        raise ValueError("Command is not supported by this firmware")
    if text in {"*", "#", "$"}:
        raise ValueError({"*": "Unknown command", "#": "Command not authorized", "$": "Invalid command"}[text])
    if "=" in text:
        return text.split("=", 1)[1].strip()
    if text.endswith("!"):
        return "OK"
    return text


def input_power_display(raw: str) -> str:
    microwatts = float(raw)
    if microwatts <= 0:
        return f"{microwatts:g} µW   (— dBm)"
    return f"{microwatts:g} µW   ({10 * math.log10(microwatts / 1000):.2f} dBm)"


def output_power_display(raw: str) -> str:
    milliwatts = float(raw)
    if milliwatts <= 0:
        return f"{milliwatts:g} mW   (— dBm)"
    return f"{milliwatts:g} mW   ({10 * math.log10(milliwatts):.2f} dBm)"


class CefaSerial:
    def __init__(self):
        self.port: serial.Serial | None = None
        self.lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return bool(self.port and self.port.is_open)

    def connect(self, port_name: str) -> None:
        self.close()
        self.port = serial.Serial(
            port_name, BAUDRATE, bytesize=8, parity="N", stopbits=1,
            timeout=0.8, write_timeout=0.8, xonxoff=False,
            rtscts=False, dsrdtr=False,
        )
        self.port.reset_input_buffer()

    def close(self) -> None:
        if self.port and self.port.is_open:
            self.port.close()
        self.port = None

    def command(self, command: str, write_allowed: bool = False) -> str:
        command = command.strip().upper()
        if "=" in command and not write_allowed:
            raise PermissionError("Write command blocked")
        if not self.connected:
            raise serial.SerialException("EDFA is not connected")
        with self.lock:
            assert self.port is not None
            self.port.reset_input_buffer()
            self.port.write((command + "\r").encode("ascii"))
            self.port.flush()
            deadline, data = time.monotonic() + 1.2, bytearray()
            while time.monotonic() < deadline:
                chunk = self.port.read(self.port.in_waiting or 1)
                if chunk:
                    data.extend(chunk)
                    if b"\r" in data or data[-1:] in b"!*/#$":
                        break
            return data.decode("ascii", errors="replace").strip()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CEFA EDFA Controller")
        self.geometry("720x500")
        self.resizable(False, False)
        self.client = CefaSerial()
        self.events: queue.Queue = queue.Queue()
        self.polling = False
        self.input_value = tk.StringVar(value="—")
        self.output_value = tk.StringVar(value="—")
        self.output_state = tk.StringVar(value="UNKNOWN")
        self.setpoint = tk.StringVar(value="33.0")
        self.connection_text = tk.StringVar(value="Disconnected")
        self._style()
        self._build_ui()
        self.refresh_ports()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(80, self._drain_events)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Reading.TLabel", font=("Segoe UI", 20, "bold"), foreground="#075EA8")
        style.configure("State.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 12, "bold"), padding=(18, 10))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="CEFA EDFA Controller", style="Title.TLabel").pack(anchor="w")
        connection = ttk.Frame(root)
        connection.pack(fill="x", pady=(18, 14))
        self.port_box = ttk.Combobox(connection, width=38, state="readonly")
        self.port_box.pack(side="left")
        ttk.Button(connection, text="Refresh", command=self.refresh_ports).pack(side="left", padx=7)
        self.connect_button = ttk.Button(connection, text="Connect", command=self.toggle_connection)
        self.connect_button.pack(side="left")
        ttk.Label(connection, textvariable=self.connection_text).pack(side="right")

        readings = ttk.Frame(root)
        readings.pack(fill="x", pady=6)
        input_box = ttk.LabelFrame(readings, text="Input Power", padding=18)
        output_box = ttk.LabelFrame(readings, text="Output Power", padding=18)
        input_box.pack(side="left", fill="both", expand=True, padx=(0, 7))
        output_box.pack(side="left", fill="both", expand=True, padx=(7, 0))
        ttk.Label(input_box, textvariable=self.input_value, style="Reading.TLabel").pack()
        ttk.Label(output_box, textvariable=self.output_value, style="Reading.TLabel").pack()

        controls = ttk.LabelFrame(root, text="Output Control", padding=16)
        controls.pack(fill="x", pady=14)
        ttk.Label(controls, text="Output state:").grid(row=0, column=0, sticky="w")
        self.state_label = ttk.Label(controls, textvariable=self.output_state, style="State.TLabel")
        self.state_label.grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(controls, text="Set power:").grid(row=1, column=0, sticky="w", pady=(14, 0))
        ttk.Entry(controls, textvariable=self.setpoint, width=10, justify="right").grid(row=1, column=1, sticky="w", padx=(10, 3), pady=(14, 0))
        ttk.Label(controls, text="dBm").grid(row=1, column=2, sticky="w", pady=(14, 0))
        self.apply_button = ttk.Button(controls, text="Apply Setpoint", command=self.apply_setpoint, state="disabled")
        self.apply_button.grid(row=1, column=3, padx=18, pady=(14, 0))
        self.on_button = ttk.Button(controls, text="OUTPUT ON", style="Big.TButton", command=self.output_on, state="disabled")
        self.off_button = ttk.Button(controls, text="OUTPUT OFF", style="Big.TButton", command=self.output_off, state="disabled")
        self.on_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 0), padx=(0, 8))
        self.off_button.grid(row=2, column=2, columnspan=2, sticky="ew", pady=(18, 0), padx=(8, 0))
        self.status = ttk.Label(root, text="Connecting does not change the output state.", foreground="#555555")
        self.status.pack(anchor="w", pady=(4, 0))

    def refresh_ports(self) -> None:
        values = [f"{p.device} — {p.description}" for p in list_ports.comports()]
        self.port_box["values"] = values
        if values and not self.port_box.get():
            self.port_box.set(next((v for v in values if v.startswith("COM5 ")), values[0]))

    def toggle_connection(self) -> None:
        if self.client.connected:
            self.disconnect()
            return
        if not self.port_box.get():
            messagebox.showwarning("No port", "Select a serial port first.")
            return
        port_name = self.port_box.get().split(" — ", 1)[0]
        try:
            self.client.connect(port_name)
            serial_number = parse_answer(self.client.command("SNU?"))
            self.connection_text.set(f"Connected · SN {serial_number}")
            self.connect_button.config(text="Disconnect")
            self._set_controls("normal")
            self.polling = True
            self._poll()
        except Exception as exc:
            self.client.close()
            messagebox.showerror("Connection failed", str(exc))

    def disconnect(self) -> None:
        self.polling = False
        self.client.close()
        self.connection_text.set("Disconnected")
        self.connect_button.config(text="Connect")
        self._set_controls("disabled")

    def _set_controls(self, state: str) -> None:
        for button in (self.apply_button, self.on_button, self.off_button):
            button.config(state=state)

    def _poll(self) -> None:
        if not self.polling or not self.client.connected:
            return
        def work() -> None:
            for key, command in (("input", "PUE?"), ("output", "PUS?"), ("state", "ASS?")):
                try:
                    self.events.put(("value", key, parse_answer(self.client.command(command))))
                except Exception as exc:
                    self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()
        self.after(1000, self._poll)

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "error":
                    self.status.config(text=event[1], foreground="#A51414")
                    continue
                if event[0] == "notice":
                    self.status.config(text=event[1], foreground="#08783E")
                    continue
                _, key, raw = event
                if key == "input":
                    self.input_value.set(input_power_display(raw))
                elif key == "output":
                    self.output_value.set(output_power_display(raw))
                elif key == "state":
                    state = {"0": "OFF", "1": "ON · ACC", "2": "ON · APC"}.get(raw, f"MODE {raw}")
                    self.output_state.set(state)
                    self.state_label.config(foreground="#08783E" if raw in {"1", "2"} else "#A51414")
        except queue.Empty:
            pass
        self.after(80, self._drain_events)

    def apply_setpoint(self) -> None:
        try:
            value = float(self.setpoint.get())
        except ValueError:
            messagebox.showerror("Invalid value", "Enter the output power in dBm.")
            return
        if not 0 <= value <= MAX_OUTPUT_DBM:
            messagebox.showerror("Out of range", f"Output power must be between 0 and {MAX_OUTPUT_DBM:g} dBm.")
            return
        if messagebox.askyesno("Confirm setpoint", f"Set the APC output power to {value:.1f} dBm?"):
            self._write(f"CPU={round(value * 10)}", f"Setpoint changed to {value:.1f} dBm")

    def output_on(self) -> None:
        text = ("Turn the optical output ON in APC mode?\n\nHigh-power laser radiation may be emitted. "
                "Confirm that the optical path, interlock and laser safety measures are ready.")
        if messagebox.askyesno("Confirm OUTPUT ON", text, icon="warning"):
            self._write("ASS=2", "Output ON command accepted")

    def output_off(self) -> None:
        if messagebox.askyesno("Confirm OUTPUT OFF", "Turn the optical output OFF?"):
            self._write("ASS=0", "Output OFF command accepted")

    def _write(self, command: str, success_text: str) -> None:
        def work() -> None:
            try:
                result = parse_answer(self.client.command(command, write_allowed=True))
                if result != "OK":
                    raise ValueError(f"Unexpected response: {result}")
                self.events.put(("notice", success_text))
            except Exception as exc:
                self.events.put(("error", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def on_close(self) -> None:
        self.polling = False
        self.client.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()

