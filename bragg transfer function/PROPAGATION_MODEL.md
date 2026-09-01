# Propagation-aware Bragg transfer-function calculator

Run the new version with:

```bash
python3 bragg_transfer_function_propagation_ui.py
```

Run its validation suite with:

```bash
python3 bragg_transfer_function_propagation_ui.py --self-test
```

The original calculator is unchanged. The new version takes the `pi/2` and
`pi` square durations or Gaussian optical-intensity FWHM values in
microseconds. It derives the nominal peak two-photon Rabi rates from the
required pulse areas. `T` is the center-to-center separation for both pulse
shapes.

For atom-to-retroreflector distance `L`, the round-trip delay is

```text
delay = 2 L / c.
```

If `I(t)` is the forward optical-intensity envelope at the atoms, the raw
two-photon Rabi envelope is

```text
Omega_raw(t) = Omega_input sqrt[I(t) I(t-delay)] / I_peak.
```

## Propagation models

- **Model A: area compensated** rescales every delayed overlap envelope to the
  ideal `pi/2 - pi - pi/2` areas. It isolates the change of pulse shape after
  experimental pulse-area calibration.
- **Model B: fixed input** keeps the peak Rabi rates inferred from the entered
  undelayed pulse widths. The overlap loss produces nonideal pulse areas. Its
  sensitivity function is evaluated from a resonant two-level propagator using
  infinitesimal phase steps and is normalized by the output fringe slope.

## Displayed transfer functions

The atomic response to the local counter-propagating phase difference is

```text
H_AI(f) = n F[ds/dt].
```

The propagation-delay phase-difference filter is

```text
D_delay(f) = 1 - exp[-i 2 pi f (2L/c)].
```

The combined transfer from source laser phase to atom phase is

```text
H_source_phase = H_AI D_delay.
```

For laser frequency noise expressed in Hz, the corresponding transfer is

```text
H_nu = H_source_phase / (i f),
```

with units rad/Hz.

## Model boundary

The dynamics backend is an effective resonant two-level model. Bragg order `n`
is an external phase-gain multiplier. Model B includes imperfect pulse areas
inside this two-level approximation, but it does not include the momentum-state
ladder, diffraction phases, Doppler detuning, AC Stark shifts, or parasitic
interferometers of a full high-order Bragg calculation.
