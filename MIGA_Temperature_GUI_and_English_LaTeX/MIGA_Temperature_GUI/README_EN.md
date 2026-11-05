# MIGA Temperature Baseline Noise — Python GUI


Use the language selector at the upper right to switch between 中文 and English. Labels, results and plots update immediately without changing inputs or rerunning the calculation. Chinese is the default; the language selection is not saved in configuration files. Existing configurations remain compatible, and JSON/CSV export fields retain their stable English keys.
Use Python 3.10+ with Tkinter, NumPy, SciPy and Matplotlib.

```bash
python -m pip install -r requirements.txt
python miga_temperature_gui.py
```

The default fast *radial* model calibrates the two-state resonant splitter and
mirror pulse areas at each source's nominal temperature, then freezes those
areas and numerically evaluates dB/dT. The model uses a 2D transverse Gaussian
cloud and a centered Gaussian Bragg coupling. Baseline Allan deviation is
`abs(dB/dT) * sigma_T`; mid-fringe apparent phase Allan deviation is the
baseline Allan deviation divided by the source's **measured absolute fringe
amplitude**. Independent sources combine as `sqrt(sigma_22**2 + sigma_21**2)`.

The GUI lets you change source temperatures, shot-to-shot Allan deviations,
measured ensemble pi/2 and pi efficiencies, measured B/A, and Rabi branches.
It also provides optional 4D phase-space tracking, a hypothetical spatial
acceptance width, plots, and export of result JSON/CSV/PNG and GUI settings.

## Default conditional output

- MIGA22: approximately 57.92 mrad
- MIGA21: approximately 45.90 mrad
- Differential: approximately 73.90 mrad

**Crucial:** the predicted mean fringe baselines and amplitudes do not
exactly reproduce the experiment, and the code has no genuine quasi-Bragg
diffraction phase. These outputs are conditional sensitivity scenarios, not
validated experimental noise attributions.

Use `python test_model.py` for convergence and smoke tests.
See `README_中文.md` for the complete parameter guide.
