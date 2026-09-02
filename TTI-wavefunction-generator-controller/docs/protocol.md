# LAN protocol decisions

Source: [manufacturer TGF3000 manual](https://resources.aimtti.com/manuals/TGF3000_Series_Instruction_Manual-Iss5.pdf), pp. 93–107 (printed page numbers).

The raw TCP port is **9221**. Send ASCII commands followed by LF. Receive LF-terminated replies, tolerating CRLF. The reader handles segmented packets, bounds reply size and total reply time, and closes the socket on timeout to prevent stale responses being attributed to a later query.

## Connection and test

Only `*IDN?` is sent during connect/test. The second comma-delimited field must be `TGF3162`. No reset, output command, coupling change or channel selection is sent during connection. The first hardware mutation prepares independent operation.

## Applying a channel

All channel operations share one reentrant lock, including queries and channel selection. Before each write transaction, collect and log existing error registers; these registers clear on read. Each command is followed by `EER?`, `QER?`, `*ESR?`. This deliberately favors error localization over maximum configuration speed.

```text
TRACKING OFF
FRQCPLSWT OFF
AMPLCPLNG OFF
OUTPUTCPLNG OFF
CHN <1|2>
MOD OFF
SWP OFF
BST OFF
AMPLRNG AUTO
DCOFFS 0
ZLOAD 50
AMPL 0.01
WAVE SINE
CHN2CONFIG MAINOUT          (channel 2 only)
OUTPUT NORMAL
MODFMDEV 0
FREQ <Hz>
AMPL <Vpp>
PHASE <degrees>
```

`OUTPUT NORMAL` selects normal polarity; it is not `OUTPUT ON`. Reducing amplitude before raising frequency avoids intermediate range violations. Clearing FM deviation before changing carrier avoids a stale deviation constraining the new carrier. This sequence is not atomic and can produce transients on a running output. It disables any pre-existing sweep or burst on the selected channel and ensures channel 2 is a main output when configuring CH2.

For AM, append:

```text
MODAMSRC INT
MODAMSHAPE SINE
MODAMFREQ <Hz>
MODAMDEPTH <percent>
MOD AM
```

For FM, append:

```text
MODFMSRC INT
MODFMSHAPE SINE
MODFMFREQ <Hz>
MODFMDEV <Hz>
MOD FM
```

Finally `*OPC?` must return `1`. Only then is local command state updated. If any command is rejected, stop immediately, disconnect and invalidate both cached channels. Earlier commands cannot be rolled back. The opposite channel is not selected or assigned a waveform; the global coupling switches are explicitly disabled to establish independence.

## Output switch

Disable the same four coupling/tracking switches, select `CHN`, and send `OUTPUT ON` or `OUTPUT OFF`. ON requires known settings in this session. OFF works with unknown settings, including an initial power-on flag. The API uses explicit booleans rather than a toggle, preventing retries from inverting the desired state.

## Readback limitation

No undocumented `FREQ?`, `AMPL?`, `OUTPUT?` or `MOD?` is sent. The opaque `*LRN?` binary setup is not treated as a documented parameter schema. Identity/status reads are real reads; channel values are only last accepted command values. Another controller or the front panel can invalidate them without detection. A reported power-on flag invalidates both channel records.

## First hardware checks still required

Confirm exact firmware compatibility, initial unusual waveform/load behavior, AM envelope semantics, the FM edge/amplitude policy, command latency, phase behavior without ALIGN and output polarity command semantics. The local test peer only verifies the software's expected conversation.
