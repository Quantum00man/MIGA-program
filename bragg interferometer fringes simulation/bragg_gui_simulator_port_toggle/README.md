# Bragg GUI Simulator With Port Toggle

This folder contains an upgraded GUI front-end that adds an upper-port / lower-port display toggle on top of the existing Bragg interferometer simulator.

## Files

- [gui_app.py](/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_gui_simulator_port_toggle/gui_app.py)
  GUI and headless entry point for the port-toggle version.
- [FORMULAS.md](/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_gui_simulator_port_toggle/FORMULAS.md)
  Complete formula reference for the simulation model.

## Main additions

- Toggle between upper-port and lower-port fringe display in the GUI.
- Export the currently displayed port together with a summary JSON and a PNG plot.
- Keep a single academically consistent simulation backend by reusing the validated core in the sibling folder [bragg_gui_simulator](/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_gui_simulator).

## Run the GUI

```bash
cd "/home/yiming/Documents/MIGA-program/bragg interferometer fringes simulation/bragg_gui_simulator_port_toggle"
python3 gui_app.py
```

## Headless examples

Upper-port export:

```bash
python3 gui_app.py --headless-run --display-port upper --output-prefix outputs/port_toggle_upper
```

Lower-port export:

```bash
python3 gui_app.py --headless-run --display-port lower --output-prefix outputs/port_toggle_lower
```

## Notes

- The lower-port display is derived from the same simulated shots as the upper port.
- The normalised lower-port population is `1 - P_upper_norm`.
- The lower-port absolute mean is reconstructed as `1 - loss_mean - upper_port_abs_mean`.
- Reported `contrast` now means the peak-to-peak fringe excursion, `P_max - P_min`.
- The formula document explains the full modeling chain in detail.
