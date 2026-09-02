# UI design and review record

## Design sources

The requested [Taste skill](https://github.com/Leonxlnx/taste-skill) (ccbc156) and [Impeccable](https://github.com/pbakaus/impeccable) (0330f61) were downloaded and read. Taste v2 explicitly excludes dashboards and dense product UI; its scope warning was respected. Impeccable's Operate guidance and craft floor governed this control interface.

The confirmed brief is a simple paired channel console: light neutral background, white working surfaces, restrained green actions, system sans text, explicit units and familiar form controls. No decorative waveform is presented as a measurement. The user approved implementation after the requirements conversation; no generated concept image is claimed as an approved design.

## Verification performed

- Headless Chrome workflow at 1440 px desktop and 390 px mobile; both full-page captures visually inspected, with no horizontal mobile overflow.
- Apply, AM/FM selection, unit conversion, independent output On/Off, pending edits, invalid AM carrier, disconnect, failed LAN test and Quick guide exercised.
- API changes update clean editors; dirty drafts survive cache refresh and explicit connection checks.
- Carrier and modulation fields accept 1 microhertz expressed as `0.000000000001 MHz`.
- Browser reported zero JavaScript errors during regression checks.

The Impeccable mechanical detector reported no regex findings, but its parser dependencies were unavailable. It did not provide a computed contrast or full accessibility certification. Claims are limited to these checks and the independent source/screenshot review.

## Independent review and correction

| Finding | Correction | Final verdict |
| --- | --- | --- |
| Clean editor disagreed with updated API state | Load fresh settings into clean editors; preserve dirty drafts | Resolved |
| Native frequency minimum ignored selected units | Scale minimum by the Hz/kHz/MHz factor | Resolved |
| Long converted amplitude clipped on mobile | Stack amplitude and phase at narrow widths | Resolved |
| Unicode external-link arrow used as an icon | Remove the arrow | Resolved |

Both viewports were recaptured. The independent reviewer returned **ship**, specifically for the four scored fixes. No approved comp or separate QUALITY BAR card was supplied, so no image-fidelity or card-based quality claim is made.

## Remaining validation

The development OS was Windows. Ubuntu is supported by portable code and documented commands; the Windows/Ubuntu CI matrix has not run remotely. Physical TGF3162 behavior remains unverified. See `hardware-validation.md`.
