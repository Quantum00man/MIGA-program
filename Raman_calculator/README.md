# Raman Transition Calculator

This project converts the original Mathematica script `Raman.txt` into a Python application for simulating Raman-driven Rabi oscillations in an atomic interferometer and tracking the atom-cloud size over the selected free-expansion interval.

The interface is written in English and is designed for experimental use: clear units, explicit parameter meanings, a direct translation of the original model, and immediate access to both the Raman simulation page and the Raman detuning page.

## What the application does

The desktop GUI computes:

1. The Raman transition probability as a function of pulse duration `tau`
2. The atom-cloud transverse root-mean-square size `sigma_r(T)` from `T = 0` to the selected free-expansion time
3. Raman detuning branches or transverse velocity using the original detuning Python logic
4. A detuning-based calibration of `alpha` and `vx` from flying-up and falling-down scan results
5. A quick differential light-shift correction from measured counter-propagating
   `delta+` and `delta-` Raman peak centers

The application preserves the structure of the original Mathematica model:

- Gaussian Raman beams with powers `P1` and `P2`
- Effective Raman coupling derived from the large detuning `desacc`
- Gaussian longitudinal velocity distribution
- Gaussian transverse spatial distribution
- Radial and velocity averaging of the transition probability

## Files

- `Raman.txt`: original Mathematica source
- `Raman deturning/Raman_deturning_4.0.py`: original standalone Raman detuning calculator retained for reference
- `Raman deturning/Raman_transition_deturning_4.0.pdf`: original detuning documentation retained for reference
- `raman_model.py`: translated physics model and numerical solver
- `raman_detuning_model.py`: integrated Raman detuning, calibration, and light-shift correction model
- `app.py`: Tkinter + Matplotlib desktop interface
- `presets.json`: local preset store created or updated when presets are saved from the GUI
- `tests/test_raman_model.py`: smoke tests for the translated model
- `tests/test_raman_detuning_model.py`: tests for the integrated detuning and calibration logic
- `docs/raman_calculator_manual.tex`: detailed LaTeX manual
- `docs/raman_calculator_manual.pdf`: rendered manual when a local LaTeX engine is available

## Default parameters inherited from `Raman.txt`

The Python translation preserves the default numerical values from the original script whenever a direct one-to-one mapping exists.

| Quantity | Default |
| --- | ---: |
| `P1` | `14.0 mW` |
| `P2` | `14.0 / 2.6 = 5.384615 mW` |
| `w0` | `11.5 mm` |
| `desacc / 2pi` | `-1000 MHz` |
| `delta2 / 2pi` | `157 MHz` |
| `gamma / 2pi` | `6.065 MHz` |
| `sigma_r(0)` | `5 mm` |
| `T` in `Ptrans[T, tau, d, w0, attn]` | `56 ms` |
| `attn` | `1` |
| `G` | `1` |

### Temperature defaults

The Mathematica file explicitly sets the transverse velocity spread to `svT = 2.65 * vrec`. In the Python application, the default transverse temperature is chosen so that:

```text
sqrt(k_B * T / M) = 2.65 * vrec
```

This gives:

```text
T_default = 2.537918 uK
```

The GUI now distinguishes:

- `Transverse temperature`: used to compute `sigma_v,T`, the transverse expansion and the radial beam convolution
- `Longitudinal temperature`: used to compute `sigma_v,L`, the longitudinal velocity-selection distribution `f(vL)`

By default the longitudinal temperature is linked to the transverse temperature. It can be released and edited independently whenever anisotropic thermal modeling is needed.

## Model equations

The Gaussian beam intensities are:

```text
I1(r) = 2 P1 / (pi w0^2) * exp(-2 r^2 / w0^2)
I2(r) = 2 P2 / (pi w0^2) * exp(-2 r^2 / w0^2)
```

The translated effective Raman Rabi frequency is:

```text
Omega_eff(r) = gamma^2 * G / attn * sqrt(I1 I2) / (2 Isat)
               * [5 / (24 desacc) + 3 / (24 (desacc + delta2))] / 2
```

The generalized Rabi frequency is:

```text
Omega_R(r, vL) = sqrt(Omega_eff(r)^2 + (k_eff vL - d)^2)
```

The longitudinal velocity distribution is:

```text
f(vL) = exp[-vL^2 / (2 sigma_v,L^2)] / (sqrt(2 pi) sigma_v,L)
```

The transverse spatial distribution after free expansion time `T` is:

```text
sigma_r(T) = sqrt(sigma_r(0)^2 + sigma_v,T^2 T^2)
h(r, T) = exp[-r^2 / (2 sigma_r(T)^2)] / (2 pi sigma_r(T)^2)
```

The Raman transition probability is evaluated as:

```text
P(T, tau) =
integral integral 2 pi r f(vL) h(r, T)
    [Omega_eff(r) / Omega_R(r, vL) * sin(Omega_R(r, vL) tau / 2)]^2
dvL dr
```

## Running the application

## Requirements

- Python `3.10+`
- `numpy`
- `scipy`
- `matplotlib`
- `tkinter` (standard on many desktop Python installations)

Install dependencies if needed:

```bash
python3 -m pip install -r requirements.txt
```

Start the GUI:

```bash
python3 app.py
```

## Main pages

The application now has two top-level pages:

- `Simulation`: Raman transition probability, cloud expansion, presets, and locked-curve comparison
- `Detuning`: Raman detuning calculator, velocity inversion, calibration of `alpha` and
  `vx`, plus a light-shift correction panel that extracts a common differential shift
  from measured counter-propagating `delta+` / `delta-` peak centers and reports both
  centers after removing it (neglecting Zeeman and frequency-reference offsets)

## Built-in presets

The GUI now includes bundled presets that can be applied, edited, and saved locally:

| Preset | Parameters changed relative to the default set |
| --- | --- |
| `Original Raman.txt Defaults` | Uses the translated Mathematica defaults |
| `Raman Down` | `P1 = 14 mW`, `P2 = 7 mW`, `w0 = 11.5 mm`, `T = 56 ms`, `desacc / 2pi = -1300 MHz` |
| `Raman Up` | `P1 = 150 mW`, `P2 = 70 mW`, `w0 = 30 mm`, `T = 78 ms` |
| `Raman Labeling` | `P1 = 150 mW`, `P2 = 70 mW`, `w0 = 30 mm`, `T = 780 ms` |

Important note:

- In these presets, the user-specified `56 ms`, `78 ms`, and `780 ms` values are mapped to the advanced parameter `Expansion time T before Raman pulse`, because the pulse-duration sweep `tau` is plotted in `us`.

## Main input fields

### Primary inputs

- `Transverse temperature (uK)`: controls the transverse velocity spread used in cloud expansion and radial averaging
- `Use a separate longitudinal temperature`: unlocks an independent longitudinal thermal input
- `Longitudinal temperature (uK)`: controls the longitudinal velocity spread used in the Raman velocity-selection term
- `Large Raman detuning desacc / 2pi (MHz)`: one-photon detuning
- `Beam power P1, P2 (mW)`: Raman beam optical powers
- `Beam waist w0 (mm)`: Gaussian waist shared by both beams
- `tau minimum, tau maximum (us)`: pulse-duration sweep range
- `Number of tau samples`: plot resolution

### Advanced model parameters

- `Expansion time T before Raman pulse (ms)`: free-expansion time used in the Raman integral
- `Initial cloud size sigma_r(0) (mm)`: initial transverse rms cloud size
- `Two-photon detuning d / 2pi (kHz)`: residual Raman detuning
- `Attenuation factor`: multiplicative suppression applied to the effective Rabi frequency
- `Coupling gain G`: multiplicative coupling factor from the original Mathematica file

### Numerical controls

- `Radial grid points`: radial quadrature resolution
- `Velocity grid points`: longitudinal quadrature resolution
- `Radial cutoff (x w0)`: upper radial integration boundary
- `Velocity cutoff (x sigma)`: truncation of the longitudinal velocity integral

### Preset workflow

- `Apply`: load the selected preset into the current fields and immediately recompute the plots
- `Save to Selected Preset`: overwrite the currently selected preset in `presets.json`
- `Save as New Preset`: create a new locally stored preset from the current valid input set
- `Delete Local Preset Copy`: remove a user-defined preset or a local override of a bundled preset

### Top-right action bar

- `Run Simulation`: compute the current parameter set
- `Reset to Defaults`: restore the translated Raman.txt defaults in the input panel
- `Export Current CSV`: export the current simulation only
- `Lock Current`: keep the current curves visible as reference traces while new simulations are run
- `Clear Locked`: remove all locked reference traces

## Outputs

The GUI provides:

- A Rabi-oscillation plot `P(T, tau)` versus `tau`
- A cloud-expansion plot `sigma_r(T)` from `0` to the selected expansion time `T`
- Locked-result overlays and automatic legends when multiple simulations are displayed at once
- Interactive plot inspection:
  - hover readout for the nearest sampled point
  - click-to-pin markers on either curve
  - double-click or `Reset Plot View` to restore the latest auto-generated view
- A derived-values panel listing:
  - velocity spreads
  - peak beam intensities
  - on-axis Raman Rabi frequency
  - estimated `pi`-pulse duration
  - numerical integration settings

## Detuning page

The `Detuning` page preserves the logic of the original `Raman_deturning_4.0.py` script and adds it as a dedicated GUI workflow.

### Calculator modes

- `vx -> Detuning`: compute all four detuning branches for a given `vx`
- `Detuning -> vx`: infer `vx` from a signed detuning, the motion direction, and the transition type

### Experimental constants

- `vz (m/s)`: vertical velocity
- `alpha (deg)`: beam angle relative to the `z` axis
- `Laser wavelength (nm)`: used to construct `k` and `keff`
- `Recoil frequency (kHz)`: two-photon recoil term

### Light-shift correction workflow

The `Light-shift Correction` panel accepts the two fitted counter-propagating Raman
peak centers measured with the current `P1` / `P2` configuration:

- `Measured delta+ center (kHz)`: the `+keff` peak center
- `Measured delta- center (kHz)`: the `-keff` peak center
- `Transition`: `F1→F2` or `F2→F1`, which selects the recoil sign

The quick correction assumes that both peaks experience the same differential light
shift. In consistent frequency units, the measured pair is modeled as

```text
delta+ = +D + signed_recoil + delta_AC
delta- = -D + signed_recoil + delta_AC
```

The application calculates

```text
measured_pair_mean = (delta+ + delta-) / 2
doppler_term       = (delta+ - delta-) / 2
delta_AC           = measured_pair_mean - signed_recoil
corrected_delta+   = delta+ - delta_AC
corrected_delta-   = delta- - delta_AC
measured_co-pro    = delta_AC
corrected_co-pro   = 0 kHz
```

After correction, the mean of the two reported peak centers is exactly the signed
recoil center: `+recoil_frequency` for `F1→F2` and `-recoil_frequency` for
`F2→F1` under the calculator's existing sign convention.

For the central co-propagating resonance, the calculator uses the approximation
`k_eff,co ≈ 0`, so its Doppler and recoil terms are neglected. Its measured center is
therefore predicted at `delta_AC`, while removal of the differential AC Stark shift
returns the center to `0 kHz`.

This is deliberately a fast experimental correction. It neglects Zeeman shifts and
frequency-reference/scan-zero offsets. Consequently, any such common offset present
in the measured pair will be interpreted as light shift. The two entered peaks must
belong to the same `mF` transition and be measured with the same Raman pulse and
`P1` / `P2` configuration.

The result tab presents the measured quantities, extracted terms, and corrected
centers with Matplotlib-rendered mathematical notation, avoiding platform-dependent
Unicode subscript and superscript glyphs. A normalized spectrum compares the measured
three-peak spectrum (two counter-pro peaks plus the central co-pro peak) with its
light-shift-corrected counterpart. The plotted
centers are the calculated values; the displayed linewidth and amplitude are schematic
and are not a fit to raw experimental samples.

The spectrum is interactive: hover for coordinates, use the mouse wheel to zoom around
the cursor, drag after selecting the toolbar pan tool, use rectangular zoom, return to
the full view with Home, and save the current figure from the Matplotlib toolbar. The
divider between the quantitative summary and spectrum can also be dragged to allocate
more space to either panel.

### Calibration workflow

The calibration tool asks for:

- the signed detuning extracted from the `flying up` scan
- the signed detuning extracted from the `falling down` scan
- the transition direction: `F1→F2` or `F2→F1`

The program then reconstructs:

- `alpha`
- `vx`

using the same detuning model as the original script. The sign of each entered detuning automatically selects the corresponding `Delta>0` or `Delta<0` branch. After calibration, the recovered `alpha` can be applied back to the detuning constants, and the recovered `vx` is copied into the calculator input for immediate reuse.

### Rabi-axis autoscaling

The plot tab includes an `Auto-scale Rabi y-axis` option. When enabled, the application scales the probability axis to the simulated signal level, which is especially useful when the transition probability stays well below unity.

## Tests

Run the smoke tests with:

```bash
python3 -m unittest discover -s tests -v
```

## Documentation

The detailed LaTeX manual source is provided here:

- `docs/raman_calculator_manual.tex`

If a LaTeX engine such as `pdflatex` is installed on the machine, the rendered PDF will be written to:

- `docs/raman_calculator_manual.pdf`

To rebuild the PDF:

```bash
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=docs docs/raman_calculator_manual.tex
```

## Notes on interpretation

- The lower plot shows the atom-cloud size over the user-selected `0` to `T` free-expansion interval.
- The Raman transition probability is computed at that same fixed expansion time `T`, matching the original `dispPos[T]` and `Ptrans[T, tau, d, w0, attn]` structure from Mathematica.
