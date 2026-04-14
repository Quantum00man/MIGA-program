# Bragg GUI Simulator

This folder contains an upgraded English-language desktop interface for the Bragg atom-interferometer fringe simulator.

## Files

- [gui_app.py](/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_gui_simulator/gui_app.py)
  Main GUI application.
- [simulator_core.py](/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_gui_simulator/simulator_core.py)
  Reusable simulation backend, config serialization, and export utilities.

## Main GUI features

- Load a JSON configuration file.
- Edit interferometer, pulse, noise, and Monte Carlo parameters directly in the interface.
- Export the current configuration to a JSON file.
- Run the simulation from the GUI.
- Display the fringe and the noise-weighted transfer-function plot in the GUI.
- Export the latest run to `CSV`, `summary.json`, and `PNG`.
- Open parameter-specific help dialogs from `?` buttons next to the editable inputs.
- Enter Lorentzian peak levels in `PSD dB` instead of linear ASD amplitude.

## Interface language

All visible labels, buttons, dialogs, and help text in the GUI are written in English.

## Run the GUI

From this folder:

```bash
python3 gui_app.py
```

## Headless verification mode

If you are on a machine without a display, you can still run the upgraded version in headless mode:

```bash
python3 gui_app.py --headless-run --output-prefix outputs/gui_demo
```

You can also supply a configuration file:

```bash
python3 gui_app.py --headless-run --config my_config.json --output-prefix outputs/my_case
```

## Model scope

The GUI keeps the same academically motivated effective model as the earlier script:

1. A two-path Bragg Mach-Zehnder description.
2. Independent pulse transfer probability, loss, diffraction phase, and shot-to-shot jitter for each pulse.
3. Laser-frequency noise and mirror vibration noise converted to phase noise through the interferometer transfer function.

It is therefore well suited for fringe studies, noise budgeting, and parameter scans. It is not yet a full momentum-lattice Bragg propagator.

## Noise-input units

The GUI now uses PSD-dB inputs consistently for the background noise terms and for Lorentzian peaks.

For laser-frequency noise:

- `white_psd_db = 10 log10(S0 / 1 Hz^2/Hz)`
- `flicker_psd_1hz_db = 10 log10(C1 / 1 Hz^2/Hz)` with `S_flicker(f) = C1 / f`
- `random_walk_psd_1hz_db = 10 log10(C2 / 1 Hz^2/Hz)` with `S_rw(f) = C2 / f^2`
- `peak psd_db = 10 log10(S_peak_center / 1 Hz^2/Hz)`

For mirror acceleration noise:

- `white_psd_db = 10 log10(S0 / 1 (m/s^2)^2/Hz)`
- `flicker_psd_1hz_db = 10 log10(C1 / 1 (m/s^2)^2/Hz)` with `S_flicker(f) = C1 / f`
- `random_walk_psd_1hz_db = 10 log10(C2 / 1 (m/s^2)^2/Hz)` with `S_rw(f) = C2 / f^2`
- `peak psd_db = 10 log10(S_peak_center / 1 (m/s^2)^2/Hz)`

The full background-plus-peak PSD is therefore

`S(f) = S0 + C1/f + C2/f^2 + sum_i S_peak_i(f)`

with

`S_peak_i(f) = S_peak_center_i / (1 + ((f - f0_i)/width_i)^2)`

This is a PSD convention, so the conversion uses `10 log10(...)`, not `20 log10(...)` unless you start from an ASD value and first square it.

Legacy compatibility is still supported: old JSON files that use linear-ASD fields (`white`, `flicker`, `random_walk`, or peak `amplitude`) are converted automatically when loaded.
