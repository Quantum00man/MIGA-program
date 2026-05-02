# Rb87 bias coils current scan simulation

This folder contains a current-scan version of the Rb87 optical molasses model. The compensation scan variable is now the physical current in each XYZ coil pair, and the script keeps the corresponding magnetic field at the atom-cloud center.

## Geometry built into this version

Each compensation axis is modeled as one symmetric square-coil pair:

- each coil has `15` turns
- each coil is a `30 cm x 30 cm` square
- the center of each coil is `20 cm` from the atom cloud
- the two coils in one axis pair generate the same field direction at the cloud center

The script assumes:

- `X` pair centers at `x = +/- 20 cm`, field along `x`
- `Y` pair centers at `y = +/- 20 cm`, field along `y`
- `Z` pair centers at `z = +/- 20 cm`, field along `z`
- positive current produces positive `Bx`, `By`, `Bz` respectively

## Current-to-field conversion

For a square coil pair, the on-axis center field is computed from the exact square-loop formula:

```text
B_pair(0) = 4 * mu0 * N * a^2 * I / [pi * (a^2 + d^2) * sqrt(2 a^2 + d^2)]
```

where:

- `N` is the number of turns per coil
- `a` is the half side length of the square
- `d` is the distance from the atom cloud to one coil center

With the default geometry in this folder:

```text
1 A -> about 296.35 mG
```

for each axis pair at the atom-cloud center.

## Files

- `rb87_bias_coils_current_scan.py`: main current-scan simulation script
- `rb87_bias_coils_current_scan_ui.py`: default Qt-based desktop UI
- `rb87_bias_coils_current_scan_ui_tk.py`: tkinter fallback UI
- `example_config.json`: editable configuration
- `outputs/`: generated automatically after a run

## Run

```bash
python rb87_bias_coils_current_scan.py --config example_config.json
```

## Launch the UI

```bash
python rb87_bias_coils_current_scan_ui.py
```

On Windows you can also double-click:

```text
launch_ui.bat
```

The default UI is a local desktop interface built with `PySide6` + interactive `matplotlib`. It provides:

- grouped parameter controls for fields, molasses, geometry, scan, and refinement
- JSON config load/save
- one-click simulation runs
- overview and dynamics figure panels
- interactive Matplotlib plots with pan/zoom/home/save tools
- mouse-hover coordinate readout on heatmaps and line plots
- a summary report and direct links to generated outputs

The UI keeps the same simulation core as the command-line tool, so the exported files remain consistent across both workflows.

If the Qt runtime still has local DLL issues on a given machine, there is also a fallback:

```bash
python rb87_bias_coils_current_scan_ui_tk.py
```

## Output

Each run writes:

- `*_scan.csv`: full 3D current scan table
- `*_overview.png`: temperature maps versus current
- `*_dynamics.png`: residual field and temperature dynamics
- `*_summary.txt`: best current setpoint and corresponding field
- `*_resolved_config.json`: exact config plus derived `mG/A` conversion

The CSV keeps both:

- scanned current values in `A`
- corresponding coil-generated fields in `mG`

## Automatic local refinement

With this geometry, `1 A` is already about `296 mG`. If your residual field is only a few tens of `mG`, the best compensation current may be close to zero. In that case, after an initial `-3 A` to `+3 A` overview scan, it is a good idea to narrow the range around the best point for a finer scan.

This version already does that automatically by default:

- first it runs the coarse `-3 A` to `+3 A` grid
- then it refines locally around the coarse best point
- the refined points are saved to `*_refined_scan.csv`

You can control this with the `refinement` block in `example_config.json`.
