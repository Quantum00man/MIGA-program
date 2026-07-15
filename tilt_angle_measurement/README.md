# Beam Tilt Noise Analyzer

Desktop tool for recording a Basler camera stream, fitting a Gaussian beam spot on a screen, and converting beam-centroid motion into Bragg beam tilt jitter.

## Features

- Basler acquisition backend via `pypylon`
- Separate `Connect Preview` and `Start Analysis` workflow for camera bring-up
- Demo backend for UI and algorithm validation without hardware
- Live Gaussian beam tracking with thresholded moments and optional 2D rotated Gaussian refinement
- Conversion from spot displacement to tilt jitter using user-provided optical path
- Session export to CSV, JSON summary, and PNG plots

## Environment

Core dependencies:

- `PyQt5`
- `numpy`
- `scipy`
- `matplotlib`

Optional Basler dependency:

- `pypylon`

## Installation

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pypylon
```

## Launch

```bash
python3 run_beam_tilt_analyzer.py
```

## Recommended workflow

1. Start in `Demo` mode to verify the GUI and export flow.
2. Switch to `Basler` mode after `pypylon` is installed and the camera is detected by the OS.
3. Click `Connect Preview` first and confirm that a live image appears before attempting analysis.
4. Adjust exposure, gain, width, height, offsets, and ROI while the preview is running.
5. Enter the optical path length from the Bragg coupling head to the screen.
6. Enter the camera-to-screen distance and the lens focal length to estimate `mm/px`, or replace it with a manual calibration value.
7. Use `Auto ROI from Brightest Spot`, then tighten the ROI so the fit stays fast and robust.
8. Capture a background with the beam blocked if you want dark-frame subtraction.
9. Click `Start Analysis` once the spot is stable, then export the recorded session when you have enough data.

## Measurement notes

- The thin-lens estimate is convenient, but manual `mm/px` calibration on the screen is preferred for publication-quality uncertainty control.
- Gaussian refinement improves rigor, but it is slower than moment-based tracking. If you need higher bandwidth, reduce the ROI size or increase `Analysis stride`.
- A smooth, diffraction-free spot is more important than a very small spot. For centroid stability, prefer an unclipped spot with a diameter of roughly `20-60 px` FWHM on the camera.
