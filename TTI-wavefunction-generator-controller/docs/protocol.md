# LAN protocol decisions

Source: [manufacturer TGF3000 manual](https://resources.aimtti.com/manuals/TGF3000_Series_Instruction_Manual-Iss5.pdf), pp. 93–107 (printed page numbers).

The raw TCP port is **9221**. Send ASCII commands followed by LF. Receive LF-terminated replies, tolerating CRLF. The reader handles segmented packets, bounds reply size and total reply time, and closes the socket on timeout to prevent stale responses being attributed to a later query.

## Connection and test

Only `*IDN?` is sent during connect/test. The second comma-delimited field must be `TGF3162`. No reset, output command, coupling change or channel selection is sent during connection.

## Applying a channel

All channel operations share one reentrant lock so channel selections cannot interleave. The application assumes the instrument is already configured for two independent main outputs; it does not change tracking, coupling, sync-output or CH2 connector modes. Commands are combined into one semicolon-separated fire-and-forget LAN write.

```text
CHN <1|2>
MOD OFF
SWP OFF
BST OFF
AMPLRNG AUTO
DCOFFS 0
ZLOAD 50
WAVE SINE
OUTPUT NORMAL
MODFMDEV 0
FREQ <Hz>
AMPL <Vpp>
PHASE <degrees>
```

`OUTPUT NORMAL` selects normal polarity; it is not `OUTPUT ON`. Clearing FM deviation before changing carrier avoids a stale deviation constraining the new carrier. The sequence disables any pre-existing sweep or burst on the selected channel.

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

The operation path sends no query and updates the local cache after the socket write succeeds. A command rejected silently by the instrument is not detected; use explicit Refresh to query identity and status registers.

## Output switch

Select `CHN`, then send `OUTPUT ON` or `OUTPUT OFF` in one write. ON requires known settings in this session. OFF works with unknown settings. The API uses explicit booleans rather than a toggle, preventing retries from inverting the desired state.

## Readback limitation

No undocumented `FREQ?`, `AMPL?`, `OUTPUT?` or `MOD?` is sent. The opaque `*LRN?` binary setup is not treated as a documented parameter schema. Identity/status reads are real reads; channel values are only last accepted command values. Another controller or the front panel can invalidate them without detection. A reported power-on flag invalidates both channel records.

## First hardware checks still required

Confirm exact firmware compatibility, initial unusual waveform/load behavior, AM envelope semantics, the FM edge/amplitude policy, command latency, phase behavior without ALIGN and output polarity command semantics. The local test peer only verifies the software's expected conversation.
