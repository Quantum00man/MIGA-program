# TOF Shape Analyzer

This small desktop app analyzes how a transimpedance amplifier low-pass response distorts the time-of-flight (TOF) signal of a vertically launched cold-atom cloud.

## What the app models

- A 1D vertical velocity distribution with mean launch velocity `v_launch`
- Ballistic flight under gravity
- A Gaussian detection region centered at the phototube height
- A cascaded first-order low-pass stage representing the TIA bandwidth limit

The ideal detector signal is computed as

`S_ideal(t) ∝ ∫ P(v_z) exp(-(z(t; v_z) - z_det)^2 / (2 sigma_probe^2)) dv_z`

with

`z(t; v_z) = v_z t - 0.5 g t^2`

and the electronics response is modeled as

`H(f) = [1 + i (f / f_c)]^(-N)`

where `N` is the number of identical first-order poles.

## Features

- Interactive desktop UI built with `Tkinter`
- Embedded `Matplotlib` plots with zoom, pan, and save tools
- Overlay of ideal and filtered TOF traces
- Gaussian-fit overlays for the filtered upward and return peaks
- Mean trajectory and cloud-spread visualization
- Distortion plot `filtered - ideal`
- Bode magnitude/phase plot of the low-pass stage
- Quantitative metrics: peak delay, attenuation, and FWHM broadening
- CSV export for the simulated traces

## Default experimental values

- Atom species: `87Rb`
- Temperature: `5 uK`
- Launch velocity: `4.26 m/s`
- Detector height: `255 mm`

These can all be changed in the UI.

## Run

```bash
python3 tof_tia_app.py
```

## Dependencies

- `numpy`
- `matplotlib`
- `tkinter` (usually bundled with Python)

## Notes

- The present model is intentionally 1D and does not include transverse expansion, probe saturation, or photon shot noise.
- If you need a closer match to a specific setup, the next sensible extensions are:
  - finite laser-sheet geometry in 2D/3D
  - a measured TIA transfer function instead of an `N`-pole approximation
  - additive detector and electronic noise
