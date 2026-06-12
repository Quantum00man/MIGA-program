# MOT4 FPGA Tester

`mot4_fpga_tester.py` is a small Tkinter UI for reproducing and documenting
intermittent MOT4/FPGA communication problems.

It is intentionally built around `tmot4`, not `gmot4`.

Why:

- `gmot4` is the interactive GTK frontend.
- `gmot4 -> Load file` only parses the `.mot` file into memory.
- `gmot4 -> Run` uses the same backend path as `tmot4 -f sequence.mot`:
  `ParseProg() -> Compile() -> Exec() -> libusb bulk transfers`.
- `tmot4` is therefore the correct target for automated, repeatable stress
  tests of the same FPGA download/trigger logic.

## Files

- UI tool: [mot4_fpga_tester.py](/home/yiming/Documents/MIGA-program/mot4ztex_debug/mot4ztex/mot4_fpga_tester.py)
- This guide: [MOT4_FPGA_TESTER.md](/home/yiming/Documents/MIGA-program/mot4ztex_debug/mot4ztex/MOT4_FPGA_TESTER.md)

## What the tool tests

The UI offers three main scenarios:

1. Internal-trigger stability loop
   Repeats `tmot4 -f your_sequence.mot` many times and records:
   - success
   - USB failures
   - non-zero exits
   - runs that exceed the timeout and look like an unexpected wait or hang

2. External-trigger arm/wait check
   Repeats `tmot4 -e -f your_sequence.mot`, observes it for a short window,
   then stops it cleanly with `SIGINT`.
   This verifies that the program can enter the armed waiting state without
   immediately failing.

3. Internal/external mode-switch cycles
   Alternates between external and internal runs to catch state leakage, for
   example:
   - external wait leaves FPGA or USB in a bad state
   - the next internal run behaves as if it were still waiting for an
     external trigger

The tool can also:

- run `tmot4 -r` before the suite
- run `tmot4 -r` after a failed step
- capture `tmot4`/`gmot4` process snapshots
- check whether `/var/lock/mot4` exists before a run
- follow `dmesg -w` during the suite and attach matching kernel lines to the
  report

## What it does not do

- It does not drive the `gmot4` GTK window.
- It does not synthesize a real hardware external trigger pulse.
- It does not delete `/var/lock/mot4`.

The lock file is intentionally left alone. Removing it by hand can hide
concurrency bugs instead of diagnosing them.

## Requirements

- Python 3 with Tkinter
- A working `tmot4` binary
- A valid `.mot` sequence file
- Optional: permission to read kernel logs with `dmesg -w`

## Running the tester

From the `mot4ztex` directory:

```bash
python3 mot4_fpga_tester.py
```

Recommended setup:

- `tmot4 executable`: point to `./tmot4`
- `.mot file`: choose the sequence you want to stress
- `Working directory`: usually the `mot4ztex` directory
- `Report root`: a directory where test reports should be stored

If you accidentally select `gmot4`, the tester tries to switch automatically
to a sibling `tmot4` in the same directory.

Recommended first pass:

- Run timeout: `90`
- External observe: `5`
- Cooldown: `0.5`
- Internal iterations: `20`
- External iterations: `5`
- Mode switch cycles: `5`
- Reset once before the suite: enabled
- Reset automatically after a failure: enabled
- Capture process/lock snapshots: enabled
- Monitor dmesg during the suite: enabled

## Reading the results

Each step is classified with one main outcome.

### `success`

The `tmot4` process exited with code `0` and no explicit USB failure markers
were seen.

### `usb_failure`

The step printed one of the USB/libusb failure markers such as:

- `USB failure at ...`
- `USB error`
- `libusb_error`
- `hardware error`

This is the clearest sign of a download or communication problem.

### `unexpected_wait_or_hang`

An internal-trigger run exceeded the configured timeout.

This is the closest automated match for the symptom:

> "the run behaves as if it were waiting for an external trigger even though
> I did not use `-e`"

The tool cannot prove that the FPGA literally entered `ST_WAIT`, because plain
`tmot4` does not print the GUI status-bar text. Still, a timeout in internal
mode is exactly the kind of event that should be investigated next.

### `armed_and_waiting`

An external-trigger run stayed alive for the observation window and was then
stopped by the tester.

This is normally a healthy outcome for the external-trigger scenario. It means
the process reached the waiting state and did not immediately fail.

### `external_completed_early`

The external-trigger run exited before the observation window ended.

Possible explanations:

- a real external trigger arrived quickly
- the sequence completed much earlier than expected
- the FPGA did not actually remain in external wait mode

### `kernel_usb_warning`

The kernel log contained a USB-side warning during the step.

Examples:

- `did not claim interface 0 before use`
- USB reset/disconnect related lines

This is useful when the user-space logs are too generic.

## Report files

Each suite creates a timestamped report directory under the configured report
root.

The report contains:

- `suite_config.json`
- `suite_results.json`
- `suite_log.txt`
- `summary.txt`
- `summary.md`

This is meant to make bug reports reproducible and comparable across runs.

## Suggested workflow for the current MOT4/FPGA bug

1. Run the internal-trigger stability loop first.
2. If you see `usb_failure`, inspect the matching `dmesg` lines.
3. If you see `unexpected_wait_or_hang` in internal mode, note:
   - whether it happened right after an external-trigger check
   - whether a reset was required to recover
4. Run the mode-switch scenario next.
5. Compare the first internal run after an external wait against a cold-start
   internal run.

That comparison is often the fastest way to confirm whether the external wait
path leaves stale FPGA state behind.

## Notes

- If `dmesg -w` is not permitted on your system, the suite still runs; kernel
  monitoring just becomes unavailable.
- If another `tmot4` or `gmot4` process is already active, the tool records
  that fact in the step notes because concurrency can invalidate the result.
- The tester is intentionally conservative: it prefers to record a suspicious
  hang rather than silently assume a successful internal trigger.
