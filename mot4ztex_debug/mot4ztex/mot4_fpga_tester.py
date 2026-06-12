#!/usr/bin/env python3
"""Tkinter UI to stress-test tmot4/FPGA communication issues.

This tool targets ``tmot4`` on purpose. ``gmot4`` is the interactive GTK UI,
but both frontends end up using the same backend path in ``Run.c`` when they
actually compile, download and trigger a sequence. ``tmot4`` is therefore the
practical target for automated, repeatable diagnosis.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import signal
import subprocess
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


LOCK_FILE = Path("/var/lock/mot4")
KERNEL_KEYWORDS = ("usb", "usbfs", "tmot4", "gmot4", "libusb", "error", "warn")
USB_FAILURE_KEYWORDS = (
    "USB failure",
    "USB error",
    "libusb_error",
    "hardware error",
)
WAIT_KEYWORDS = (
    "Waiting for ext. trigger",
    "external trigger",
)


@dataclass
class SuiteConfig:
    executable: str
    mot_file: str
    workdir: str
    report_root: str
    run_timeout_s: float
    external_observe_s: float
    cooldown_s: float
    internal_iterations: int
    external_iterations: int
    mode_switch_cycles: int
    auto_reset_before_suite: bool
    reset_after_failure: bool
    monitor_dmesg: bool
    capture_process_state: bool
    run_internal_stability: bool
    run_external_arm_check: bool
    run_mode_switch: bool


@dataclass
class StepResult:
    scenario: str
    index: int
    command: list[str]
    mode: str
    started_at: str
    ended_at: str
    duration_s: float
    outcome: str
    returncode: Optional[int]
    timed_out: bool
    notes: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    pre_snapshot: dict = field(default_factory=dict)
    post_snapshot: dict = field(default_factory=dict)
    dmesg_excerpt: list[str] = field(default_factory=list)


class KernelLogMonitor:
    """Optional `dmesg -w` collector."""

    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.lines: list[str] = []
        self.lock = threading.Lock()
        self.proc: Optional[subprocess.Popen[str]] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        cmd = ["dmesg", "-w"]
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self.log_callback("Kernel monitor unavailable: `dmesg` not found.")
            self.proc = None
            return

        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()
        self.log_callback("Kernel monitor started with: " + " ".join(cmd))

    def _reader_loop(self) -> None:
        assert self.proc is not None
        assert self.proc.stdout is not None
        for raw_line in self.proc.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            lower = line.lower()
            if any(keyword in lower for keyword in KERNEL_KEYWORDS):
                with self.lock:
                    self.lines.append(line)
                    if len(self.lines) > 5000:
                        self.lines = self.lines[-5000:]
                self.log_callback("[dmesg] " + line)

    def mark(self) -> int:
        with self.lock:
            return len(self.lines)

    def slice_from(self, index: int) -> list[str]:
        with self.lock:
            return self.lines[index:]

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None


class Mot4FpgaTesterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MOT4 FPGA Tester")
        self.root.geometry("1220x860")

        self.script_dir = Path(__file__).resolve().parent
        default_executable = self.script_dir / "tmot4"
        default_mot = self._find_default_mot()
        default_report_root = self.script_dir / "test_reports"

        self.ui_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.results: list[StepResult] = []
        self.suite_log_lines: list[str] = []
        self.report_dir: Optional[Path] = None

        self.executable_var = tk.StringVar(value=str(default_executable))
        self.mot_file_var = tk.StringVar(value=str(default_mot) if default_mot else "")
        self.workdir_var = tk.StringVar(value=str(self.script_dir))
        self.report_root_var = tk.StringVar(value=str(default_report_root))

        self.run_timeout_var = tk.StringVar(value="90")
        self.external_observe_var = tk.StringVar(value="5")
        self.cooldown_var = tk.StringVar(value="0.5")

        self.internal_iterations_var = tk.StringVar(value="20")
        self.external_iterations_var = tk.StringVar(value="5")
        self.mode_switch_cycles_var = tk.StringVar(value="5")

        self.auto_reset_before_suite_var = tk.BooleanVar(value=True)
        self.reset_after_failure_var = tk.BooleanVar(value=True)
        self.monitor_dmesg_var = tk.BooleanVar(value=True)
        self.capture_process_state_var = tk.BooleanVar(value=True)

        self.run_internal_stability_var = tk.BooleanVar(value=True)
        self.run_external_arm_check_var = tk.BooleanVar(value=True)
        self.run_mode_switch_var = tk.BooleanVar(value=True)

        self.status_var = tk.StringVar(value="Idle")
        self.summary_var = tk.StringVar(value="No runs yet.")

        self._build_ui()
        self.root.after(100, self._drain_ui_queue)

    def _build_ui(self) -> None:
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        top = ttk.Frame(root, padding=10)
        top.grid(row=0, column=0, sticky="nsew")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)

        path_frame = ttk.LabelFrame(top, text="Paths", padding=10)
        path_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        path_frame.columnconfigure(1, weight=1)

        self._path_row(path_frame, 0, "tmot4 executable", self.executable_var, self._browse_executable)
        self._path_row(path_frame, 1, ".mot file", self.mot_file_var, self._browse_mot)
        self._path_row(path_frame, 2, "Working directory", self.workdir_var, self._browse_workdir)
        self._path_row(path_frame, 3, "Report root", self.report_root_var, self._browse_report_root)

        runtime_frame = ttk.LabelFrame(top, text="Runtime", padding=10)
        runtime_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        runtime_frame.columnconfigure(1, weight=1)

        self._entry_row(runtime_frame, 0, "Run timeout (s)", self.run_timeout_var)
        self._entry_row(runtime_frame, 1, "External observe (s)", self.external_observe_var)
        self._entry_row(runtime_frame, 2, "Cooldown between runs (s)", self.cooldown_var)
        self._entry_row(runtime_frame, 3, "Internal iterations", self.internal_iterations_var)
        self._entry_row(runtime_frame, 4, "External iterations", self.external_iterations_var)
        self._entry_row(runtime_frame, 5, "Mode switch cycles", self.mode_switch_cycles_var)

        options_frame = ttk.LabelFrame(top, text="Scenarios and options", padding=10)
        options_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        options_frame.columnconfigure(0, weight=1)
        options_frame.columnconfigure(1, weight=1)

        left = ttk.Frame(options_frame)
        left.grid(row=0, column=0, sticky="nw")
        ttk.Checkbutton(left, text="Run internal-trigger stability loop", variable=self.run_internal_stability_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(left, text="Run external-trigger arm/wait check", variable=self.run_external_arm_check_var).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(left, text="Run internal/external mode-switch cycles", variable=self.run_mode_switch_var).grid(row=2, column=0, sticky="w")

        right = ttk.Frame(options_frame)
        right.grid(row=0, column=1, sticky="nw")
        ttk.Checkbutton(right, text="Reset once before the suite", variable=self.auto_reset_before_suite_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(right, text="Reset automatically after a failure", variable=self.reset_after_failure_var).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(right, text="Capture process/lock snapshots", variable=self.capture_process_state_var).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(right, text="Monitor dmesg during the suite", variable=self.monitor_dmesg_var).grid(row=3, column=0, sticky="w")

        controls = ttk.Frame(root, padding=(10, 0, 10, 10))
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(5, weight=1)

        self.start_button = ttk.Button(controls, text="Start Suite", command=self.start_suite)
        self.start_button.grid(row=0, column=0, padx=(0, 6))
        self.stop_button = ttk.Button(controls, text="Stop After Current Step", command=self.stop_suite, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=6)
        self.reset_button = ttk.Button(controls, text="Run Reset Only", command=self.run_reset_only)
        self.reset_button.grid(row=0, column=2, padx=6)
        self.open_report_button = ttk.Button(controls, text="Open Report Folder", command=self.open_report_folder)
        self.open_report_button.grid(row=0, column=3, padx=6)

        ttk.Label(controls, textvariable=self.status_var).grid(row=0, column=4, padx=(12, 12), sticky="w")
        ttk.Label(controls, textvariable=self.summary_var, anchor="w").grid(row=0, column=5, sticky="ew")

        middle = ttk.Frame(root, padding=(10, 0, 10, 10))
        middle.grid(row=2, column=0, sticky="nsew")
        middle.columnconfigure(0, weight=3)
        middle.columnconfigure(1, weight=2)
        middle.rowconfigure(0, weight=1)

        results_frame = ttk.LabelFrame(middle, text="Step Results", padding=8)
        results_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)

        columns = ("scenario", "mode", "outcome", "rc", "duration", "notes")
        self.result_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=14)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        for name, width in (
            ("scenario", 170),
            ("mode", 70),
            ("outcome", 210),
            ("rc", 55),
            ("duration", 80),
            ("notes", 520),
        ):
            self.result_tree.heading(name, text=name)
            self.result_tree.column(name, width=width, anchor="w")
        tree_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=self.result_tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.result_tree.configure(yscrollcommand=tree_scroll.set)

        log_frame = ttk.LabelFrame(middle, text="Live Log", padding=8)
        log_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = ScrolledText(log_frame, wrap="word", font=("Courier New", 10))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")

    def _path_row(self, parent, row: int, label: str, variable: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=2, padx=(8, 0), pady=3)

    def _entry_row(self, parent, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=variable, width=16).grid(row=row, column=1, sticky="w", pady=3)

    def _browse_executable(self) -> None:
        path = filedialog.askopenfilename(
            title="Select tmot4 executable",
            initialdir=self.workdir_var.get() or str(self.script_dir),
        )
        if path:
            self.executable_var.set(path)
            self.workdir_var.set(str(Path(path).resolve().parent))

    def _browse_mot(self) -> None:
        path = filedialog.askopenfilename(
            title="Select .mot file",
            filetypes=[("MOT sequence", "*.mot"), ("All files", "*.*")],
            initialdir=self.workdir_var.get() or str(self.script_dir),
        )
        if path:
            self.mot_file_var.set(path)

    def _browse_workdir(self) -> None:
        path = filedialog.askdirectory(
            title="Select working directory",
            initialdir=self.workdir_var.get() or str(self.script_dir),
        )
        if path:
            self.workdir_var.set(path)

    def _browse_report_root(self) -> None:
        path = filedialog.askdirectory(
            title="Select report root",
            initialdir=self.report_root_var.get() or str(self.script_dir),
        )
        if path:
            self.report_root_var.set(path)

    def _find_default_mot(self) -> Optional[Path]:
        candidates = sorted(self.script_dir.glob("*.mot"))
        return candidates[0] if candidates else None

    def _append_log(self, line: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        rendered = f"[{timestamp}] {line}\n"
        self.suite_log_lines.append(rendered)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", rendered)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                event, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                break

            if event == "log":
                self._append_log(str(payload))
            elif event == "status":
                self.status_var.set(str(payload))
            elif event == "summary":
                self.summary_var.set(str(payload))
            elif event == "step":
                self._add_step_row(payload)
            elif event == "suite_finished":
                self._finish_ui(payload)

        self.root.after(100, self._drain_ui_queue)

    def _add_step_row(self, result: StepResult) -> None:
        note_text = " | ".join(result.notes) if result.notes else ""
        self.result_tree.insert(
            "",
            "end",
            values=(
                result.scenario,
                result.mode,
                result.outcome,
                "" if result.returncode is None else result.returncode,
                f"{result.duration_s:.2f}",
                note_text,
            ),
        )

    def _finish_ui(self, payload: dict) -> None:
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.reset_button.configure(state="normal")
        self.status_var.set("Idle")
        self.summary_var.set(payload["summary"])
        if payload.get("report_dir"):
            self.report_dir = Path(payload["report_dir"])
            self._append_log("Report written to: " + str(self.report_dir))

    def _emit(self, event: str, payload: object) -> None:
        self.ui_queue.put((event, payload))

    def _parse_float(self, text: str, field_name: str) -> float:
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a number.") from exc

    def _parse_int(self, text: str, field_name: str) -> int:
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc

    def _validate_config(self) -> SuiteConfig:
        executable = Path(self.executable_var.get()).expanduser()
        mot_file = Path(self.mot_file_var.get()).expanduser().resolve()
        workdir = Path(self.workdir_var.get()).expanduser().resolve()
        report_root = Path(self.report_root_var.get()).expanduser().resolve()

        if executable.name == "gmot4":
            sibling_tmot4 = executable.with_name("tmot4")
            if sibling_tmot4.exists() and os.access(sibling_tmot4, os.X_OK):
                executable = sibling_tmot4
                self.executable_var.set(str(executable))
            else:
                raise ValueError(
                    "gmot4 was selected, but this tester needs tmot4 for automation. "
                    "No executable tmot4 was found next to gmot4."
                )
        elif executable.name != "tmot4":
            raise ValueError(
                "Select tmot4 in the executable field. "
                "If you start from gmot4, point the tester to the sibling tmot4 binary."
            )
        if not executable.exists():
            raise ValueError("tmot4 executable not found.")
        if not os.access(executable, os.X_OK):
            raise ValueError("tmot4 is not executable.")
        if not mot_file.exists():
            raise ValueError(".mot file not found.")
        if not workdir.exists():
            raise ValueError("Working directory not found.")

        executable = executable if executable.is_absolute() else (workdir / executable)

        config = SuiteConfig(
            executable=str(executable),
            mot_file=str(mot_file),
            workdir=str(workdir),
            report_root=str(report_root),
            run_timeout_s=self._parse_float(self.run_timeout_var.get(), "Run timeout"),
            external_observe_s=self._parse_float(self.external_observe_var.get(), "External observe"),
            cooldown_s=self._parse_float(self.cooldown_var.get(), "Cooldown"),
            internal_iterations=self._parse_int(self.internal_iterations_var.get(), "Internal iterations"),
            external_iterations=self._parse_int(self.external_iterations_var.get(), "External iterations"),
            mode_switch_cycles=self._parse_int(self.mode_switch_cycles_var.get(), "Mode switch cycles"),
            auto_reset_before_suite=self.auto_reset_before_suite_var.get(),
            reset_after_failure=self.reset_after_failure_var.get(),
            monitor_dmesg=self.monitor_dmesg_var.get(),
            capture_process_state=self.capture_process_state_var.get(),
            run_internal_stability=self.run_internal_stability_var.get(),
            run_external_arm_check=self.run_external_arm_check_var.get(),
            run_mode_switch=self.run_mode_switch_var.get(),
        )

        if not any(
            (
                config.run_internal_stability,
                config.run_external_arm_check,
                config.run_mode_switch,
            )
        ):
            raise ValueError("Select at least one scenario.")

        return config

    def start_suite(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return

        try:
            config = self._validate_config()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self.result_tree.delete(*self.result_tree.get_children())
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.results = []
        self.suite_log_lines = []
        self.stop_event.clear()

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.reset_button.configure(state="disabled")
        self.summary_var.set("Suite running...")
        self.status_var.set("Running")

        self.worker_thread = threading.Thread(target=self._run_suite, args=(config,), daemon=True)
        self.worker_thread.start()

    def stop_suite(self) -> None:
        self.stop_event.set()
        self._emit("log", "Stop requested. The suite will stop after the current step.")

    def run_reset_only(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        try:
            config = self._validate_config()
        except ValueError as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return

        self.result_tree.delete(*self.result_tree.get_children())
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.results = []
        self.suite_log_lines = []
        self.stop_event.clear()

        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.reset_button.configure(state="disabled")
        self.summary_var.set("Reset-only run in progress...")
        self.status_var.set("Running")

        self.worker_thread = threading.Thread(target=self._run_reset_only_suite, args=(config,), daemon=True)
        self.worker_thread.start()

    def open_report_folder(self) -> None:
        target = self.report_dir or Path(self.report_root_var.get())
        if not target.exists():
            messagebox.showinfo("Open report folder", f"Path does not exist yet:\n{target}")
            return

        if os.name == "posix":
            subprocess.Popen(["xdg-open", str(target)])
        else:
            messagebox.showinfo("Open report folder", str(target))

    def _run_reset_only_suite(self, config: SuiteConfig) -> None:
        monitor = None
        try:
            report_dir = self._prepare_report_dir(config)
            self.report_dir = report_dir
            result = self._run_reset_step(config, 1, None)
            self.results.append(result)
            self._emit("step", result)
            summary = self._build_summary(self.results)
            self._write_report_files(config, report_dir, summary)
            self._emit("suite_finished", {"summary": summary, "report_dir": str(report_dir)})
        finally:
            if monitor:
                monitor.stop()

    def _run_suite(self, config: SuiteConfig) -> None:
        monitor: Optional[KernelLogMonitor] = None
        try:
            report_dir = self._prepare_report_dir(config)
            self.report_dir = report_dir

            if config.monitor_dmesg:
                monitor = KernelLogMonitor(log_callback=lambda line: self._emit("log", line))
                monitor.start()

            if config.auto_reset_before_suite and not self.stop_event.is_set():
                result = self._run_reset_step(config, 1, monitor)
                self.results.append(result)
                self._emit("step", result)
                if self._result_failed(result) and config.reset_after_failure:
                    self._emit("log", "Initial reset failed. Continuing, but results may be unreliable.")

            if config.run_internal_stability and not self.stop_event.is_set():
                self._emit("log", "Starting internal-trigger stability loop.")
                for index in range(1, config.internal_iterations + 1):
                    if self.stop_event.is_set():
                        break
                    result = self._run_internal_step(config, index, monitor)
                    self.results.append(result)
                    self._emit("step", result)
                    self._emit("summary", self._build_summary(self.results))
                    if self._result_failed(result) and config.reset_after_failure:
                        reset_result = self._run_reset_step(config, index, monitor)
                        self.results.append(reset_result)
                        self._emit("step", reset_result)
                    self._cooldown(config.cooldown_s)

            if config.run_external_arm_check and not self.stop_event.is_set():
                self._emit("log", "Starting external-trigger arm/wait checks.")
                for index in range(1, config.external_iterations + 1):
                    if self.stop_event.is_set():
                        break
                    result = self._run_external_wait_step(config, index, monitor)
                    self.results.append(result)
                    self._emit("step", result)
                    self._emit("summary", self._build_summary(self.results))
                    if self._result_failed(result) and config.reset_after_failure:
                        reset_result = self._run_reset_step(config, index, monitor)
                        self.results.append(reset_result)
                        self._emit("step", reset_result)
                    self._cooldown(config.cooldown_s)

            if config.run_mode_switch and not self.stop_event.is_set():
                self._emit("log", "Starting internal/external mode-switch cycles.")
                for index in range(1, config.mode_switch_cycles + 1):
                    if self.stop_event.is_set():
                        break
                    ext_result = self._run_external_wait_step(config, index, monitor, scenario="mode_switch_external")
                    self.results.append(ext_result)
                    self._emit("step", ext_result)
                    self._emit("summary", self._build_summary(self.results))
                    if self._result_failed(ext_result) and config.reset_after_failure:
                        reset_result = self._run_reset_step(config, index, monitor)
                        self.results.append(reset_result)
                        self._emit("step", reset_result)
                        self._cooldown(config.cooldown_s)
                    if self.stop_event.is_set():
                        break
                    int_result = self._run_internal_step(config, index, monitor, scenario="mode_switch_internal")
                    self.results.append(int_result)
                    self._emit("step", int_result)
                    self._emit("summary", self._build_summary(self.results))
                    if self._result_failed(int_result) and config.reset_after_failure:
                        reset_result = self._run_reset_step(config, index, monitor)
                        self.results.append(reset_result)
                        self._emit("step", reset_result)
                    self._cooldown(config.cooldown_s)

            summary = self._build_summary(self.results)
            self._write_report_files(config, report_dir, summary)
            self._emit("suite_finished", {"summary": summary, "report_dir": str(report_dir)})
        except Exception as exc:  # pragma: no cover - defensive reporting
            self._emit("log", f"Unhandled exception: {exc}")
            summary = self._build_summary(self.results)
            if self.report_dir:
                self._write_report_files(config, self.report_dir, summary)
            self._emit("suite_finished", {"summary": summary or "Suite aborted.", "report_dir": str(self.report_dir) if self.report_dir else ""})
        finally:
            if monitor:
                monitor.stop()

    def _prepare_report_dir(self, config: SuiteConfig) -> Path:
        root = Path(config.report_root)
        root.mkdir(parents=True, exist_ok=True)
        directory = root / ("mot4_fpga_suite_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _run_internal_step(
        self,
        config: SuiteConfig,
        index: int,
        monitor: Optional[KernelLogMonitor],
        scenario: str = "internal_stability",
    ) -> StepResult:
        command = [config.executable, "-f", config.mot_file]
        result = self._execute_step(
            scenario=scenario,
            index=index,
            command=command,
            mode="internal",
            workdir=config.workdir,
            timeout_s=config.run_timeout_s,
            monitor=monitor,
            observe_external_s=None,
            capture_snapshot=config.capture_process_state,
        )
        if result.timed_out:
            result.outcome = "unexpected_wait_or_hang"
            result.notes.append(
                "Internal-trigger run exceeded the timeout. This matches the 'unexpected wait' symptom."
            )
        return result

    def _run_external_wait_step(
        self,
        config: SuiteConfig,
        index: int,
        monitor: Optional[KernelLogMonitor],
        scenario: str = "external_arm_check",
    ) -> StepResult:
        command = [config.executable, "-e", "-f", config.mot_file]
        result = self._execute_step(
            scenario=scenario,
            index=index,
            command=command,
            mode="external",
            workdir=config.workdir,
            timeout_s=config.run_timeout_s,
            monitor=monitor,
            observe_external_s=config.external_observe_s,
            capture_snapshot=config.capture_process_state,
        )
        return result

    def _run_reset_step(
        self,
        config: SuiteConfig,
        index: int,
        monitor: Optional[KernelLogMonitor],
    ) -> StepResult:
        command = [config.executable, "-r"]
        return self._execute_step(
            scenario="reset",
            index=index,
            command=command,
            mode="reset",
            workdir=config.workdir,
            timeout_s=max(10.0, min(config.run_timeout_s, 30.0)),
            monitor=monitor,
            observe_external_s=None,
            capture_snapshot=config.capture_process_state,
        )

    def _execute_step(
        self,
        scenario: str,
        index: int,
        command: list[str],
        mode: str,
        workdir: str,
        timeout_s: float,
        monitor: Optional[KernelLogMonitor],
        observe_external_s: Optional[float],
        capture_snapshot: bool,
    ) -> StepResult:
        started = datetime.now()
        self._emit("status", f"Running {scenario} #{index}")
        self._emit("log", f"Launching {scenario} #{index}: {shlex.join(command)}")
        pre_snapshot = self._collect_snapshot() if capture_snapshot else {}
        if pre_snapshot.get("active_processes"):
            self._emit("log", "Active mot processes detected before launch: " + ", ".join(pre_snapshot["active_processes"]))

        dmesg_mark = monitor.mark() if monitor else 0
        proc = subprocess.Popen(
            command,
            cwd=workdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stdout_thread = threading.Thread(target=self._pipe_reader, args=(proc.stdout, stdout_lines, "stdout", scenario, index), daemon=True)
        stderr_thread = threading.Thread(target=self._pipe_reader, args=(proc.stderr, stderr_lines, "stderr", scenario, index), daemon=True)
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        armed_wait_observed = False
        notes: list[str] = []

        if observe_external_s is None:
            try:
                proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                notes.append("Process did not exit before the timeout.")
                self._graceful_interrupt(proc, notes)
        else:
            deadline = time.time() + observe_external_s
            while time.time() < deadline and proc.poll() is None and not self.stop_event.is_set():
                time.sleep(0.1)

            if proc.poll() is None:
                armed_wait_observed = True
                notes.append(
                    f"Process stayed alive for {observe_external_s:.1f}s, which means it remained armed/waiting for an external trigger."
                )
                self._graceful_interrupt(proc, notes)
            else:
                notes.append("External-mode process exited before the observation window ended.")

        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        ended = datetime.now()

        stdout_text = "".join(stdout_lines)
        stderr_text = "".join(stderr_lines)
        combined_text = "\n".join(part for part in (stdout_text, stderr_text) if part)

        returncode = proc.poll()
        if returncode is None:
            timed_out = True
            notes.append("Process still alive after graceful stop; forcing kill.")
            proc.kill()
            proc.wait(timeout=2.0)
            returncode = proc.returncode

        dmesg_excerpt = monitor.slice_from(dmesg_mark) if monitor else []
        post_snapshot = self._collect_snapshot() if capture_snapshot else {}

        outcome = self._classify_outcome(
            mode,
            returncode,
            timed_out,
            combined_text,
            dmesg_excerpt,
            observe_external_s,
            armed_wait_observed,
        )
        notes.extend(self._extra_notes(mode, pre_snapshot, post_snapshot, combined_text, dmesg_excerpt, timed_out))

        result = StepResult(
            scenario=scenario,
            index=index,
            command=command,
            mode=mode,
            started_at=started.isoformat(timespec="seconds"),
            ended_at=ended.isoformat(timespec="seconds"),
            duration_s=(ended - started).total_seconds(),
            outcome=outcome,
            returncode=returncode,
            timed_out=timed_out,
            notes=notes,
            stdout=stdout_text,
            stderr=stderr_text,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            dmesg_excerpt=dmesg_excerpt,
        )
        return result

    def _classify_outcome(
        self,
        mode: str,
        returncode: Optional[int],
        timed_out: bool,
        combined_text: str,
        dmesg_excerpt: list[str],
        observe_external_s: Optional[float],
        armed_wait_observed: bool,
    ) -> str:
        lower_text = combined_text.lower()
        lower_dmesg = "\n".join(dmesg_excerpt).lower()

        if any(keyword.lower() in lower_text for keyword in USB_FAILURE_KEYWORDS):
            return "usb_failure"
        if "did not claim interface 0 before use" in lower_dmesg:
            return "kernel_usb_warning"
        if timed_out and mode == "internal":
            return "unexpected_wait_or_hang"
        if mode == "external" and observe_external_s is not None and armed_wait_observed:
            if returncode in (0, 255, -signal.SIGINT):
                return "armed_and_waiting"
        if "parse error" in lower_text or "this is not a program" in lower_text:
            return "parse_or_input_error"
        if mode == "external" and observe_external_s is not None and returncode == 0:
            return "external_completed_early"
        if returncode == 0:
            return "success"
        if returncode == -signal.SIGINT and mode == "external":
            return "armed_and_waiting"
        if returncode == -signal.SIGINT and timed_out:
            return "stopped_after_timeout"
        if returncode is None:
            return "no_returncode"
        return "nonzero_exit"

    def _extra_notes(
        self,
        mode: str,
        pre_snapshot: dict,
        post_snapshot: dict,
        combined_text: str,
        dmesg_excerpt: list[str],
        timed_out: bool,
    ) -> list[str]:
        notes: list[str] = []
        if pre_snapshot.get("active_processes"):
            notes.append("Another tmot4/gmot4 process was already active before launch.")
        if pre_snapshot.get("lock_exists") and not pre_snapshot.get("active_processes"):
            notes.append("Lock file existed before launch without a visible tmot4/gmot4 process.")
        if mode == "internal" and timed_out and not any(keyword in combined_text for keyword in WAIT_KEYWORDS):
            notes.append("No explicit wait message was captured; the process may have hung before printing anything.")
        if any("did not claim interface 0 before use" in line.lower() for line in dmesg_excerpt):
            notes.append("Kernel reported USB interface use without a claimed interface.")
        if any("usb disconnect" in line.lower() or "reset high-speed usb device" in line.lower() for line in dmesg_excerpt):
            notes.append("Kernel log suggests a physical USB reset/disconnect during the step.")
        if post_snapshot.get("active_processes"):
            notes.append("A tmot4/gmot4 process remained active after the step.")
        return notes

    def _graceful_interrupt(self, proc: subprocess.Popen[str], notes: list[str]) -> None:
        if proc.poll() is not None:
            return
        notes.append("Sending SIGINT to stop the current tmot4 process.")
        try:
            proc.send_signal(signal.SIGINT)
            proc.wait(timeout=4.0)
        except subprocess.TimeoutExpired:
            notes.append("SIGINT did not stop the process; sending SIGKILL.")
            proc.kill()
            proc.wait(timeout=2.0)

    def _pipe_reader(
        self,
        stream,
        target: list[str],
        label: str,
        scenario: str,
        index: int,
    ) -> None:
        if stream is None:
            return
        for raw_line in stream:
            line = raw_line.rstrip()
            target.append(raw_line)
            if line:
                self._emit("log", f"[{scenario} #{index} {label}] {line}")

    def _collect_snapshot(self) -> dict:
        snapshot = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "lock_exists": LOCK_FILE.exists(),
            "lock_path": str(LOCK_FILE),
            "active_processes": self._pgrep("tmot4") + self._pgrep("gmot4"),
        }
        if LOCK_FILE.exists():
            try:
                stat = LOCK_FILE.stat()
                snapshot["lock_size"] = stat.st_size
                snapshot["lock_mtime"] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            except OSError:
                snapshot["lock_size"] = None
        return snapshot

    def _pgrep(self, name: str) -> list[str]:
        try:
            completed = subprocess.run(
                ["pgrep", "-a", name],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return []
        if completed.returncode != 0:
            return []
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]

    def _cooldown(self, seconds: float) -> None:
        if seconds <= 0:
            return
        deadline = time.time() + seconds
        while time.time() < deadline and not self.stop_event.is_set():
            time.sleep(0.1)

    def _build_summary(self, results: list[StepResult]) -> str:
        if not results:
            return "No steps executed."

        counter = Counter(result.outcome for result in results)
        headline = ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))

        findings: list[str] = []
        if any(result.outcome == "unexpected_wait_or_hang" for result in results):
            findings.append("internal trigger sometimes hangs or waits unexpectedly")
        if any(result.outcome == "usb_failure" for result in results):
            findings.append("USB communication failures were reproduced")
        if any(result.outcome == "kernel_usb_warning" for result in results):
            findings.append("kernel-side USB warnings were captured")
        if any("Another tmot4/gmot4 process was already active before launch." in result.notes for result in results):
            findings.append("concurrent processes were present during at least one run")

        if findings:
            return headline + " | Findings: " + "; ".join(findings)
        return headline

    def _result_failed(self, result: StepResult) -> bool:
        return result.outcome not in ("success", "armed_and_waiting")

    def _write_report_files(self, config: SuiteConfig, report_dir: Path, summary: str) -> None:
        report_dir.mkdir(parents=True, exist_ok=True)

        (report_dir / "suite_config.json").write_text(
            json.dumps(asdict(config), indent=2),
            encoding="utf-8",
        )
        (report_dir / "suite_results.json").write_text(
            json.dumps([asdict(result) for result in self.results], indent=2),
            encoding="utf-8",
        )
        (report_dir / "suite_log.txt").write_text("".join(self.suite_log_lines), encoding="utf-8")
        (report_dir / "summary.txt").write_text(summary + "\n", encoding="utf-8")
        (report_dir / "summary.md").write_text(self._render_markdown_summary(config, summary), encoding="utf-8")

    def _render_markdown_summary(self, config: SuiteConfig, summary: str) -> str:
        lines = [
            "# MOT4 FPGA Tester Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- tmot4: `{config.executable}`",
            f"- Sequence: `{config.mot_file}`",
            f"- Working directory: `{config.workdir}`",
            "",
            "## Summary",
            "",
            summary,
            "",
            "## Step Results",
            "",
            "| Scenario | Mode | Outcome | RC | Duration (s) | Notes |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
        for result in self.results:
            notes = "<br>".join(result.notes) if result.notes else ""
            rc = "" if result.returncode is None else str(result.returncode)
            lines.append(
                f"| {result.scenario} | {result.mode} | {result.outcome} | {rc} | {result.duration_s:.2f} | {notes} |"
            )

        lines.extend(
            [
                "",
                "## Interpretation Hints",
                "",
                "- `usb_failure`: tmot4 reported a libusb-side failure.",
                "- `unexpected_wait_or_hang`: an internal-trigger run exceeded the timeout. This is the closest automated match for the 'waiting for external trigger without -e' symptom.",
                "- `armed_and_waiting`: external-trigger mode stayed alive during the observation window, which means tmot4/FPGA entered the armed wait state.",
                "- `kernel_usb_warning`: the kernel reported a USB-side warning in `dmesg` during the step.",
            ]
        )
        return "\n".join(lines) + "\n"


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    Mot4FpgaTesterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
