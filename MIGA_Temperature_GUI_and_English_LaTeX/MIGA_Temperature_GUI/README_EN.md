# MIGA Temperature Baseline Noise — Python GUI


Use the language selector at the upper right to switch between 中文 and English. Labels, results and plots update immediately without changing inputs or rerunning the calculation. Chinese is the default; the language selection is not saved in configuration files. Existing configurations remain compatible, and JSON/CSV export fields retain their stable English keys.
Use Python 3.10+ with Tkinter, NumPy, SciPy and Matplotlib.

```bash
python -m pip install -r requirements.txt
python miga_temperature_gui.py  # temperature noise
python miga_launch_gui.py       # launch velocity / position noise
```

On Windows use `launch_temperature_windows.bat` and `launch_velocity_windows.bat`; on macOS/Linux use `launch_temperature_unix.sh` and `launch_velocity_unix.sh`. The existing generic launchers still open the temperature GUI. Both apps share the model and settings format but run as separate windows.

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

## Launch velocity and position noise

The dedicated launch noise window reuses the existing geometry, source temperature, pulse efficiencies, Rabi branches and measured fringe B/A. It adds detection arrival times and Allan deviations, per-source vertical offsets and optional effective wavefront curvature. Old settings files still load; new ones also save the launch settings. In that window, click Calculate launch noise, then export its own JSON, CSV or PNG.

The arrival-time conversion assumes descending detection and attributes timing jitter solely to launch-velocity jitter, with no launch-height or detector jitter. A middle pulse time of zero places each source at its own nominal apex; a positive value uses one common laboratory time. Pulse times, optics, temperature and pulse areas are fixed during velocity/offset scans. The vertical offset is the nominal cloud center minus the beam center; the old temperature-model x offset is not used here. A nonzero detection acceptance is a fixed Gaussian weighting centered on the nominal middle cloud location and is only a proxy for the actual detector.

The baseline phase response uses measured absolute amplitude and the selected sign of the local fringe slope. The optional quadratic wavefront uses a point-cloud center trajectory and an assumed effective two-photon curvature, not an ensemble-coherent diffraction calculation; 200 m is an example and zero means a plane wave. Wavefront and baseline sensitivities are added with signs before taking their absolute value, because they share the same launch jitter. Different sources are combined in quadrature only under the stated independence assumption.

Results are conditional scenarios, not measured or validated noise budgets. The calculation checks finite differences and two 4D Gauss–Hermite integration orders. The primary position order is n and residual velocity order is min(10,max(4,ceil(n/8))); warnings indicate disagreement at the nominal offset. To check scan points, rerun with those offsets as nominal inputs. A nonlinear response across one velocity Allan also produces a warning: first-order propagation can miss noise. Review and increase orders for difficult branches and geometries. Run `python test_launch.py` for regression and convergence tests. `sample_launch_scenario.json` uses an illustrative 200 m wavefront, not a measured curvature. See the Chinese README for detailed conventions.

When wavefront is disabled, the table says “Disabled” and total response excludes it; the curvature plot always shows scenarios with the wavefront enabled. Recalculate after changing the checkbox. JSON uses numerical zero for a disabled contribution and records the switch in `settings.wavefront_enabled`.
