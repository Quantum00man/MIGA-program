# Horizontal Bragg Gradiometer Designer

This workspace contains a Python simulator for a horizontal two-point atom gradiometer with first-order Bragg diffraction and a small beam tilt relative to the x axis.

## Files

- `gravity_gradient_simulator.py`: Tkinter GUI with four interactive Matplotlib plots.
- `miga_physics.py`: Physics backend for fringe inversion, Bragg-axis projection, and source-mass design models.
- `miga_horizontal_gradiometer_note.tex`: Detailed LaTeX note describing the physical model.

## Run

```bash
python3 gravity_gradient_simulator.py
```

## Implemented logic

- Fringe period or phase-slope input is first converted into acceleration along the Bragg axis.
- The code then reports the effective x-axis acceleration inferred from that tilted Bragg measurement using the user-defined angle `alpha`.
- The current source-mass model computes the field at MIGA21 and MIGA22 for a point mass at arbitrary `(x, y)`.
- The inverse-design model computes the mass required at each position along `y = 0` to reproduce the measured x-gradient.
- The forward model scans the source mass at one fixed position and reports how the two accelerations and the gradient vary.

## Interaction

The GUI includes the standard Matplotlib toolbar for pan, zoom, save, and reset actions. Hovering or clicking a plotted curve shows live coordinates in the results panel.
