# Dual Atom Interferometer Fringe and Lissajous Simulator

This folder contains a small GUI tool for simulating two atom-interferometer fringes in a gradient-measurement configuration and plotting the corresponding Lissajous figure.

## Files

- `gui_app.py`: Tkinter + Matplotlib graphical interface.
- `simulator_core.py`: simulation model, summary generation, and CSV/JSON export helpers.

## Fringe definitions

Each interferometer can be defined in either of two modes:

- `Cosine parameters`
- `Custom formula`

The built-in cosine model is:

`P(T) = offset + 0.5 * pp * cos(2π T² / period + phase)`

where:

- `T` is the pulse separation in milliseconds.
- `period` is entered in `T²` units (`ms²`).
- `phase` is the static phase parameter in radians.
- `offset` is the fringe center.
- `pp` is the peak-to-peak amplitude.

In `Custom formula` mode, the expression is evaluated on the same `T²` axis and can use:

- `t2_ms2`, `t_ms`
- `phase_scan_rad`
- `period_t2_ms2`, `phase_rad`, `offset`, `peak_to_peak`
- `pi`, `e`
- math helpers such as `sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `clip`, `where`, `minimum`, `maximum`

## Lissajous modes

The left plot always shows the fringes against `T² (ms²)`.

The right plot supports two Lissajous trajectories:

- `Use T scan`: the original mode, traced while scanning `T`.
- `Fix T and scan phase`: keeps `T` fixed and scans `phase_scan_rad` to generate another Lissajous curve.

When phase-scan mode is active, the exported data bundle also includes a `*_phase_scan.csv` file.

## Run

From this folder:

```bash
python3 gui_app.py
```

## Outputs

- The GUI can save a publication-style figure as `PNG` or `PDF`.
- The GUI can export the `T`-scan traces as `CSV`.
- In phase-scan mode it also exports a second `CSV` file for the fixed-`T` phase sweep.
- A sidecar `JSON` file stores the active configuration and summary.
- The GUI can load a previously exported `JSON` file, restore the controls, and recompute the plots.
