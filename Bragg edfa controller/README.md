# CEFA EDFA Controller

Minimal English desktop controller for the Keopsys CEFA B202 amplifier.

- Live input power (`PUE?`)
- Live output power (`PUS?`)
- APC output-power setpoint (`CPU=`)
- Output ON in APC mode (`ASS=2`)
- Output OFF (`ASS=0`)

The serial connection is 19200 baud, 8N1, no flow control, terminated by carriage return. Connecting does not change the optical output state. Every output change requires confirmation.

Launch with `start_controller.bat`.
