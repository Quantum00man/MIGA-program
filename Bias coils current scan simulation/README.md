# Rb87 bias coils current scan simulation

This folder contains a current-scan version of the Rb87 optical molasses model. The compensation scan variable is now the physical current in each XYZ coil pair, and the script keeps the corresponding magnetic field at the chosen molasses-cloud position. It also includes an optional 3D-MOT anti-Helmholtz coil-pair model so that an off-center cloud can feel a residual quadrupole field during switch-off.

## Geometry built into this version

Each compensation axis is modeled as one symmetric square-coil pair:

- each coil has `15` turns
- each coil is a `30 cm x 30 cm` square
- the center of each coil is `20 cm` from the default cloud position
- the two coils in one axis pair generate the same field direction near the symmetric center

The script assumes:

- `X` pair centers at `x = +/- 20 cm`, field along `x`
- `Y` pair centers at `y = +/- 20 cm`, field along `y`
- `Z` pair centers at `z = +/- 20 cm`, field along `z`
- positive current produces positive `Bx`, `By`, `Bz` respectively

## Molasses position

The simulation now includes:

```text
molasses_position_mm = [x0, y0, z0]
```

with default:

```text
[0.0, 0.0, 0.0]
```

This means:

- when `molasses_position_mm = [0, 0, 0]`, the cloud center is at the geometric center of the three coil pairs
- when you move the cloud away from the origin, the code evaluates the compensation field at that shifted point
- the model is still a single-point cloud-center model for temperature evolution, but it can now also draw local spatial field cuts around that cloud center

## 3D MOT gradient coils

The code now includes a separate `mot_gradient_coils` block for the 3D-MOT pair. In the current default example:

- the pair is modeled as a circular anti-Helmholtz coil pair
- the coil-pair axis is along the line `y = z`
- the two coil centers are at `+/- 10 cm` from the origin along that axis
- each coil has `50` turns
- the nominal MOT current is `7 A`
- the switch-off transient uses the same decay time constant `mot_decay_tau_ms` as the earlier scalar MOT switch-off field

The current default example also assumes:

- `radius_cm = 10 cm`

because the radius was not yet specified explicitly. This is just a configurable default, not a hard-coded requirement.

At the origin, an ideal anti-Helmholtz pair gives zero field and nonzero gradient. If the cloud is displaced from the origin, the script evaluates the local MOT residual field at the shifted cloud center and adds it to the optical-molasses field model.

## Compensation-coil current-to-field conversion

The code now computes a full `3 x 3` current-to-field matrix at the chosen `molasses_position_mm` using finite-segment Biot-Savart integration for the square loops:

```text
[Bx]   [Mxx Mxy Mxz] [Ix]
[By] = [Myx Myy Myz] [Iy]
[Bz]   [Mzx Mzy Mzz] [Iz]
```

At the symmetric origin, this matrix is nearly diagonal and reduces to the familiar on-axis center-field conversion. For a square coil pair at the origin, the on-axis center field is:

```text
B_pair(0) = 4 * mu0 * N * a^2 * I / [pi * (a^2 + d^2) * sqrt(2 a^2 + d^2)]
```

where:

- `N` is the number of turns per coil
- `a` is the half side length of the square
- `d` is the distance from the atom cloud to one coil center

With the default geometry in this folder and `molasses_position_mm = [0, 0, 0]`:

```text
1 A -> about 296.35 mG
```

for each axis pair at the cloud center.

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
- configurable molasses cloud position `X/Y/Z` in `mm`
- configurable 3D-MOT gradient-coil geometry and axis direction
- local spatial-field probe settings
- JSON config load/save
- one-click simulation runs
- overview and dynamics figure panels
- spatial field-curve panel
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
- `*_spatial_field.png`: local magnetic-field curves around the cloud center
- `*_summary.txt`: best current setpoint and corresponding field
- `*_resolved_config.json`: exact config plus the derived current-to-field matrix at the chosen molasses position

The CSV keeps both:

- scanned current values in `A`
- corresponding coil-generated fields in `mG`

The resolved config also keeps:

- the compensation-coil `3 x 3` field matrix at the chosen cloud center
- the MOT gradient field at the cloud center at `t = 0`
- the local MOT gradient Jacobian near the cloud center

## Automatic local refinement

With this geometry, `1 A` is already about `296 mG`. If your residual field is only a few tens of `mG`, the best compensation current may be close to zero. In that case, after an initial `-3 A` to `+3 A` overview scan, it is a good idea to narrow the range around the best point for a finer scan.

This version already does that automatically by default:

- first it runs the coarse `-3 A` to `+3 A` grid
- then it refines locally around the coarse best point
- the refined points are saved to `*_refined_scan.csv`

You can control this with the `refinement` block in `example_config.json`.
