#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


THIS_DIR = Path(__file__).resolve().parent
BASE_GUI_DIR = THIS_DIR.parent / "bragg_gui_simulator"

if str(BASE_GUI_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_GUI_DIR))


def load_module(module_name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


import simulator_core as base_core

legacy_gui = load_module("bragg_gui_simulator_base_gui", BASE_GUI_DIR / "gui_app.py")

tk = legacy_gui.tk
ttk = legacy_gui.ttk
filedialog = legacy_gui.filedialog
messagebox = legacy_gui.messagebox


PORT_CHOICES = {
    "upper": {
        "label": "Upper Port",
        "ylabel": "Normalised upper-port population",
        "slug": "upper_port",
    },
    "lower": {
        "label": "Lower Port",
        "ylabel": "Normalised lower-port population",
        "slug": "lower_port",
    },
}


def selected_port_arrays(results: dict[str, Any], port: str) -> dict[str, np.ndarray]:
    upper_norm_mean = np.asarray(results["port_b_norm_mean"])
    upper_norm_std = np.asarray(results["port_b_norm_std"])
    upper_abs_mean = np.asarray(results["port_b_abs_mean"])
    loss_mean = np.asarray(results["loss_mean"])

    lower_norm_mean = 1.0 - upper_norm_mean
    lower_norm_std = upper_norm_std
    lower_abs_mean = np.clip(1.0 - loss_mean - upper_abs_mean, 0.0, 1.0)

    if port == "upper":
        return {
            "norm_mean": upper_norm_mean,
            "norm_std": upper_norm_std,
            "abs_mean": upper_abs_mean,
        }
    if port == "lower":
        return {
            "norm_mean": lower_norm_mean,
            "norm_std": lower_norm_std,
            "abs_mean": lower_abs_mean,
        }
    raise ValueError(f"Unsupported port selection: {port}")


def selected_port_fit(
    cfg: base_core.BraggSimulationConfig,
    results: dict[str, Any],
    port: str,
) -> dict[str, float]:
    arrays = selected_port_arrays(results, port)
    return base_core.fit_cosine(
        scan_phase_rad=np.asarray(results["scan_phase_rad"]),
        y=arrays["norm_mean"],
        bragg_order=cfg.interferometer.bragg_order,
    )


def selected_port_summary(
    cfg: base_core.BraggSimulationConfig,
    results: dict[str, Any],
    port: str,
) -> str:
    arrays = selected_port_arrays(results, port)
    fit = selected_port_fit(cfg, results, port)
    label = PORT_CHOICES[port]["label"]
    return "\n".join(
        [
            f"Displayed port: {label}",
            f"Laser phase sigma: {results['laser_phase_std_rad']:.6f} rad",
            f"Mirror vibration sigma: {results['vibration_phase_std_rad']:.6f} rad",
            f"Normalised fringe offset: {fit['offset']:.6f}",
            f"Normalised fringe amplitude: {fit['amplitude']:.6f}",
            f"Normalised peak-to-peak contrast: {fit['contrast']:.6f}",
            f"Phase offset: {fit['phase_offset_rad']:.6f} rad",
            f"Displayed-port minimum: {arrays['norm_mean'].min():.6f}",
            f"Displayed-port maximum: {arrays['norm_mean'].max():.6f}",
        ]
    )


def plot_selected_port_on_axes(
    cfg: base_core.BraggSimulationConfig,
    results: dict[str, Any],
    axes: Any,
    port: str,
) -> None:
    arrays = selected_port_arrays(results, port)
    fit = selected_port_fit(cfg, results, port)
    scan = np.asarray(results["scan_phase_rad"])
    label = PORT_CHOICES[port]["label"]
    fitted = fit["offset"] + fit["amplitude"] * np.cos(
        cfg.interferometer.bragg_order * scan + fit["phase_offset_rad"]
    )

    fringe_axis, noise_axis = axes
    fringe_axis.clear()
    fringe_axis.plot(scan, arrays["norm_mean"], color="tab:blue", label=f"{label} Monte Carlo fringe")
    fringe_axis.fill_between(
        scan,
        arrays["norm_mean"] - arrays["norm_std"],
        arrays["norm_mean"] + arrays["norm_std"],
        color="tab:blue",
        alpha=0.18,
        linewidth=0.0,
        label="shot scatter",
    )
    fringe_axis.plot(scan, fitted, color="tab:red", linestyle="--", label="cosine fit")
    fringe_axis.set_xlabel("Scanned optical phase phi0 [rad]")
    fringe_axis.set_ylabel(PORT_CHOICES[port]["ylabel"])
    fringe_axis.set_title(
        f"{label} Bragg-Mach-Zehnder fringe\n"
        f"peak-to-peak contrast={fit['contrast']:.3f}, phase offset={fit['phase_offset_rad']:.3f} rad"
    )
    fringe_axis.legend()
    fringe_axis.grid(alpha=0.25)

    freq = np.asarray(results["frequency_hz"])
    noise_axis.clear()
    noise_axis.loglog(
        freq,
        results["laser_integrand_rad2_per_hz"],
        color="tab:green",
        label="laser-frequency noise contribution",
    )
    noise_axis.loglog(
        freq,
        results["vibration_integrand_rad2_per_hz"],
        color="tab:orange",
        label="mirror-vibration contribution",
    )
    noise_axis.set_xlabel("Fourier frequency [Hz]")
    noise_axis.set_ylabel("|H(f)|^2 S_phi(f) [rad^2/Hz]")
    noise_axis.set_title("Phase-noise weighting by interferometer transfer function")
    noise_axis.legend()
    noise_axis.grid(alpha=0.25, which="both")


def save_display_csv(output_prefix: Path, results: dict[str, Any]) -> Path:
    csv_path = output_prefix.with_suffix(".csv")
    upper_norm_mean = np.asarray(results["port_b_norm_mean"])
    upper_norm_std = np.asarray(results["port_b_norm_std"])
    upper_abs_mean = np.asarray(results["port_b_abs_mean"])
    loss_mean = np.asarray(results["loss_mean"])
    lower_norm_mean = 1.0 - upper_norm_mean
    lower_norm_std = upper_norm_std
    lower_abs_mean = np.clip(1.0 - loss_mean - upper_abs_mean, 0.0, 1.0)

    data = np.column_stack(
        [
            results["scan_phase_rad"],
            upper_abs_mean,
            lower_abs_mean,
            upper_norm_mean,
            upper_norm_std,
            lower_norm_mean,
            lower_norm_std,
            loss_mean,
        ]
    )
    header = (
        "scan_phase_rad,"
        "upper_port_abs_mean,"
        "lower_port_abs_mean,"
        "upper_port_norm_mean,"
        "upper_port_norm_std,"
        "lower_port_norm_mean,"
        "lower_port_norm_std,"
        "loss_mean"
    )
    np.savetxt(csv_path, data, delimiter=",", header=header, comments="")
    return csv_path


def save_display_summary(
    output_prefix: Path,
    cfg: base_core.BraggSimulationConfig,
    results: dict[str, Any],
    port: str,
) -> Path:
    summary_path = output_prefix.with_suffix(".summary.json")
    payload = {
        "config": base_core.config_to_dict(cfg),
        "display_port": port,
        "laser_phase_std_rad": results["laser_phase_std_rad"],
        "vibration_phase_std_rad": results["vibration_phase_std_rad"],
        "upper_port_fit": selected_port_fit(cfg, results, "upper"),
        "lower_port_fit": selected_port_fit(cfg, results, "lower"),
        "display_port_fit": selected_port_fit(cfg, results, port),
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return summary_path


def save_display_plot(
    output_prefix: Path,
    cfg: base_core.BraggSimulationConfig,
    results: dict[str, Any],
    port: str,
) -> Path | None:
    if base_core.plt is None:
        return None
    fig, axes = base_core.plt.subplots(2, 1, figsize=(9, 8), constrained_layout=True)
    plot_selected_port_on_axes(cfg, results, axes, port)
    plot_path = output_prefix.with_suffix(".png")
    fig.savefig(plot_path, dpi=180)
    base_core.plt.close(fig)
    return plot_path


def save_display_outputs(
    cfg: base_core.BraggSimulationConfig,
    results: dict[str, Any],
    port: str,
    output_prefix: str | Path | None = None,
) -> dict[str, Path | None]:
    prefix = Path(output_prefix if output_prefix is not None else cfg.simulation.output_prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    return {
        "csv": save_display_csv(prefix, results),
        "summary": save_display_summary(prefix, cfg, results, port),
        "plot": save_display_plot(prefix, cfg, results, port),
    }


class PortToggleSimulationApp(legacy_gui.SimulationApp):
    def _build_result_panel(self, parent: Any) -> None:
        self.display_port_var = tk.StringVar(value="upper")

        options_frame = ttk.LabelFrame(parent, text="Display Options", padding=12)
        options_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        options_frame.columnconfigure(3, weight=1)

        ttk.Label(options_frame, text="Displayed output port").grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Radiobutton(
            options_frame,
            text="Upper port",
            value="upper",
            variable=self.display_port_var,
            command=self.refresh_port_display,
        ).grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Radiobutton(
            options_frame,
            text="Lower port",
            value="lower",
            variable=self.display_port_var,
            command=self.refresh_port_display,
        ).grid(row=0, column=2, sticky="w", padx=(0, 12))
        ttk.Label(
            options_frame,
            text="The lower-port fringe is computed from the same simulated shots and displayed as a complementary output.",
            wraplength=620,
            justify="left",
        ).grid(row=0, column=3, sticky="w")

        summary_frame = ttk.LabelFrame(parent, text="Run Summary", padding=12)
        summary_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        summary_frame.columnconfigure(0, weight=1)

        self.summary_text = tk.Text(summary_frame, height=10, wrap="word", state="disabled")
        self.summary_text.grid(row=0, column=0, sticky="ew")

        self.plot_host = ttk.Frame(parent)
        self.plot_host.grid(row=2, column=0, sticky="nsew")
        self.plot_host.columnconfigure(0, weight=1)
        self.plot_host.rowconfigure(0, weight=1)

        result_notes = (
            "This version reuses the same effective two-port Bragg model and lets you switch "
            "between upper-port and lower-port fringe visualisation without rerunning the simulation."
        )
        ttk.Label(parent, text=result_notes, wraplength=720, justify="left").grid(
            row=3, column=0, sticky="ew", pady=(8, 0)
        )

    def populate_form(self, cfg: base_core.BraggSimulationConfig) -> None:
        super().populate_form(cfg)
        if hasattr(self, "display_port_var"):
            self.display_port_var.set("upper")

    def refresh_port_display(self) -> None:
        if self.current_results is None or self.current_run_config is None:
            return
        port = self.display_port_var.get()
        self.set_summary_text(selected_port_summary(self.current_run_config, self.current_results, port))
        if self.has_plot_backend and self.fringe_axis is not None and self.noise_axis is not None and self.canvas is not None:
            plot_selected_port_on_axes(
                self.current_run_config,
                self.current_results,
                (self.fringe_axis, self.noise_axis),
                port,
            )
            self.canvas.draw_idle()
        fit = selected_port_fit(self.current_run_config, self.current_results, port)
        self.set_status(
            f"Simulation finished. Displaying {PORT_CHOICES[port]['label'].lower()}. "
            f"Peak-to-peak contrast={fit['contrast']:.4f}, phase offset={fit['phase_offset_rad']:.4f} rad."
        )

    def poll_run_queue(self) -> None:
        try:
            status, payload = self.run_queue.get_nowait()
        except legacy_gui.queue.Empty:
            if self.is_running:
                self.after(120, self.poll_run_queue)
            return

        self.is_running = False
        self.set_controls_enabled(True)

        if status == "error":
            self.set_status("Simulation failed.")
            messagebox.showerror("Simulation failed", payload, parent=self)
            return

        cfg, results = payload
        self.current_run_config = cfg
        self.current_results = results
        self.refresh_port_display()

    def export_results_dialog(self) -> None:
        if self.current_results is None or self.current_run_config is None:
            messagebox.showinfo("No results", "Run a simulation before exporting results.", parent=self)
            return

        port = self.display_port_var.get()
        current_var, _ = self.parameter_vars["simulation.output_prefix"]
        initial = legacy_gui.strip_output_extensions(current_var.get().strip() or "outputs/bragg_gui_port_toggle_run")
        initial_path = Path(initial)
        suggested_name = f"{initial_path.name}_{PORT_CHOICES[port]['slug']}"

        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Export results",
            initialfile=suggested_name,
            initialdir=str(initial_path.parent),
            filetypes=[("All files", "*.*")],
        )
        if not chosen:
            return

        output_prefix = legacy_gui.strip_output_extensions(chosen)
        current_var.set(output_prefix)
        cfg = base_core.update_output_prefix(self.current_run_config, output_prefix)
        try:
            output_paths = save_display_outputs(cfg, self.current_results, port, output_prefix=output_prefix)
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export results:\n{exc}", parent=self)
            return

        lines = [f"display_port: {port}"]
        lines.extend(f"{key}: {value}" for key, value in output_paths.items() if value is not None)
        if output_paths.get("plot") is None:
            lines.append("plot: matplotlib is not available in this Python environment")
        messagebox.showinfo("Export complete", "\n".join(lines), parent=self)
        self.set_status(f"Exported {PORT_CHOICES[port]['label'].lower()} results to prefix {output_prefix}")


def run_headless(config_path: str | None, output_prefix: str | None, display_port: str) -> int:
    if display_port not in PORT_CHOICES:
        raise ValueError(f"Unsupported display port: {display_port}")
    cfg = base_core.load_config(config_path)
    if output_prefix:
        cfg = base_core.update_output_prefix(cfg, legacy_gui.strip_output_extensions(output_prefix))
    results = base_core.simulate_fringe(cfg)
    output_paths = save_display_outputs(cfg, results, display_port, output_prefix=cfg.simulation.output_prefix)
    print(selected_port_summary(cfg, results, display_port))
    for key, value in output_paths.items():
        print(f"{key}: {value}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Port-toggle GUI front-end for the Bragg atom-interferometer fringe simulator."
    )
    parser.add_argument("--headless-run", action="store_true", help="Run the simulator without launching the GUI.")
    parser.add_argument("--config", type=str, help="JSON configuration file used for headless mode.")
    parser.add_argument("--output-prefix", type=str, help="Override the output prefix in headless mode.")
    parser.add_argument(
        "--display-port",
        type=str,
        choices=sorted(PORT_CHOICES.keys()),
        default="upper",
        help="Select which output port is rendered and exported.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.headless_run:
        return run_headless(args.config, args.output_prefix, args.display_port)

    app = PortToggleSimulationApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
