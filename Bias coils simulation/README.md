# Rb87 bias coils optical molasses simulation

This folder contains a first-pass Python model for the effect of XYZ compensation coils on Rb87 optical molasses after the 3D MOT quadrupole field is switched off.

## Model included in the script

The script combines four ingredients:

1. A `3x3` compensation-coil matrix that maps your control values to magnetic field at the atom cloud.
2. A time-dependent residual field after MOT switch-off:
   `B(t) = B_stray + B_comp + B_switch_off * exp(-t / tau)`.
3. A semi-empirical polarization-gradient-cooling suppression factor:
   `eta(t) = 1 / (1 + (|B(t)| / B_width)^2)`.
4. A temperature evolution model during molasses:
   `dT/dt = -(T - T_eq(B)) / tau_cool(B)`.

This is not a full quantum Monte Carlo wavefunction simulation. It is designed as a practical experimental fitting and scan tool that you can calibrate using your real measurements.

## Files

- `rb87_bias_coils_pgc_simulation.py`: main simulation script
- `example_config.json`: editable example configuration
- `outputs/`: generated automatically after a run

## Run

```bash
python rb87_bias_coils_pgc_simulation.py
```

Or run with the editable config:

```bash
python rb87_bias_coils_pgc_simulation.py --config example_config.json
```

If you want a fresh template config:

```bash
python rb87_bias_coils_pgc_simulation.py --write-default-config my_config.json
```

## Output

Each run writes:

- `*_scan.csv`: 3D scan table
- `*_overview.png`: XY / XZ / YZ maps and 1D cuts through the best point
- `*_dynamics.png`: residual field and temperature dynamics
- `*_summary.txt`: best compensation point and main metrics
- `*_resolved_config.json`: the exact config used in the run

## Parameters you should replace with your experiment values

The most important items to calibrate are:

- `fields.static_stray_field_mG`
- `fields.mot_switch_off_field_mG`
- `fields.mot_decay_tau_ms`
- `coils.coil_matrix_mG_per_unit`
- `molasses.detuning_mhz`
- `molasses.saturation_parameter_per_beam`
- `molasses.molasses_duration_ms`
- `molasses.zero_field_temperature_uK`
- `molasses.failure_temperature_uK`

## How to interpret the coil matrix

If your compensation values are already in field units, you can keep the identity matrix.

If your compensation values are currents or DAC values, fill:

```text
coil_matrix_mG_per_unit =
[
  [dBx/dUx, dBx/dUy, dBx/dUz],
  [dBy/dUx, dBy/dUy, dBy/dUz],
  [dBz/dUx, dBz/dUy, dBz/dUz]
]
```

This allows cross-axis coupling and non-ideal alignment.

## Suggested next calibration step

If you already have measured molasses temperature versus compensation current, use that dataset to fit:

- the coil matrix
- the switch-off field vector
- the decay time constant
- the effective `B_width`

Once those are matched, this script becomes a useful predictor for the best XYZ compensation point.
