# MIGA Temperature-Induced Baseline Phase Noise — English Overleaf Project

This project is the **English-language version** of the full derivation
previously provided in Chinese. It preserves the physical framework,
step-by-step four-path calculation of the fringe baseline and amplitude,
Maxwell–Boltzmann transverse phase-space distribution, ensemble integration,
finite-difference temperature sensitivity, and conditional Allan-noise examples.
It also includes a short section connecting the derivation to the separate
interactive Python GUI.

## Importing into Overleaf

1. Select **New Project → Upload Project**.
2. Upload the ZIP file directly.
3. Use **pdfLaTeX** as the compiler (the Overleaf default).
4. Set `main.tex` as the main file and select **Recompile**.

The project requires no special fonts, shell escape, or external images.

## Contents

- `main.tex`: complete English derivation, path table, equations, conditional
  MIGA22/MIGA21 numbers, caveats, and model extension discussion.
- `radial_demo.py`: minimal NumPy-based example of the original Gaussian
  radial integral. Run `python radial_demo.py` after installing NumPy.
- `README.md`: instructions and scope notes.

## Scientific limitation

The historical **58.0 / 46.1 / 74.1 mrad** values are conditional results
obtained from old assumed temperature-to-baseline slopes. A separately tested
fast radial GUI model gives about **57.92 / 45.90 / 73.90 mrad** under specified
assumptions and calibration, but it still does not match both measured fringe
baselines and amplitudes. Neither result is a validated experimental noise
budget, nor does the two-state model predict real quasi-Bragg diffraction phase.
