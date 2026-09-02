---
name: TGF3162 Controller
description: A clear, paired-channel laboratory workstation.
colors:
  accent: "#126352"
  accent-hover: "#0b4c3f"
  soft: "#e8f2ef"
  bg: "#f3f5f7"
  surface: "#fff"
  ink: "#202b35"
  muted: "#576674"
  line: "#d9e0e5"
  control-border: "#b7c3cc"
  danger: "#a92828"
  warning: "#80571b"
typography:
  body:
    fontFamily: '"Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif'
    fontSize: "15px"
    fontWeight: 400
  title:
    fontSize: "18px"
    fontWeight: 650
  label:
    fontSize: "13px"
    fontWeight: 400
  compact-label:
    fontSize: "12px"
  control:
    fontSize: "14px"
    fontWeight: 600
  quantity:
    fontSize: "18px"
    lineHeight: 1.3
rounded:
  surface: "8px"
  control: "6px"
spacing:
  compact: "8px"
  related: "12px"
  inset: "18px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "10px 17px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "10px 17px"
  quantity:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "46px"
  channel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.surface}"
---

# Design System: TGF3162 Controller

## Overview

**Creative North Star: "Paired channel workstation"**

A light, quiet operating surface for independent laboratory outputs. White instrument panels, restrained green actions, and readable numeric fields support deliberate edits. English labels and local system fonts keep the interface usable on Windows and Ubuntu without network assets.

**Key Characteristics:**

- Equal visual weight for both channels.
- Values, units, draft state, and output state remain distinct.
- Flat surfaces and compact, gently rounded controls.

Extracted from `tgf_controller/static/styles.css`, `index.html`, and `app.js`; surface composition is recorded separately in `docs/surface-brief.md`.

## Colors

The palette combines cool neutral surfaces with a deep green action accent.

### Primary

Accent marks primary actions, accepted-state text, active modulation, and enabled outputs. Accent-hover supplies button feedback; soft supplies restrained selected-state and LAN-notice fills.

### Neutral

Bg surrounds white surface panels. Ink carries values and headings; muted carries labels and supporting text. Line divides regions; control-border gives editable controls a stronger boundary.

Danger marks failures; warning marks unapplied changes and unknown outputs. These semantic colors always accompany readable text.

**The Explicit State Rule.** Color reinforces a written state; it never substitutes for one.

## Typography

Use the inherited system sans stack recorded above. Channel titles and primary quantity values share the largest recurring text size; control labels and supporting text step down through the compact scale. Paragraphs use a comfortable line height (1.55). Values and activity times use tabular numerals.

The page heading is a single surface-level title, not a reusable display treatment. Unit labels remain smaller than the adjacent number and stay inside its control boundary.

**The Number and Unit Rule.** Keep each editable quantity visibly paired with its unit.

## Layout

The working area is centered with a maximum width (1220px). Channels form equal columns with a gap (22px), then stack below (850px). Desktop panel interiors use the section inset; medium layouts reduce horizontal insets to (20px).

Connection controls wrap at (1050px). At (540px) and below, outer gutters become (16px), channel interiors use the inset token, and carrier amplitude/phase and modulation field pairs stack into full-width fields. Connection actions use a two-column grid. Keep channel actions within their own panel; flex layout aligns desktop Apply rows despite differing modulation content.

## Elevation & Depth

There are no box shadows. White panels, pale state fills, and thin borders establish hierarchy. Focus is an interaction indicator, using an outline (3px solid #298273) with an offset (3px), not simulated elevation.

## Shapes

Surface corners use the surface radius; buttons, quantity groups, notices, and connection inputs use the control radius. Small segmented options are tighter (4px modulation, 5px output). Borders are generally (1px). Status dots are circular and paired with text.

## Components

### Buttons

Primary buttons use the accent and secondary buttons use a white fill with control-border. Both have a minimum height (42px). Hover darkens primary actions or adds a pale neutral secondary fill. Background transitions last (160ms); reduced-motion preferences remove transitions. Disabled buttons halve opacity and use the unavailable cursor. Text actions remain understated and underline on hover.

### Inputs / Fields

Quantity controls combine a large tabular number and an inline unit selector or fixed unit. A thin internal divider separates selectable units; the surrounding border turns accent on focus within. Carrier controls use the quantity height; modulation controls compact to (40px). Frequency minima track the selected unit, preserving the same physical lower bound. Inline hints explain ranges and amplitude equivalence.

### Cards / Containers

Channel panels share identical structure: title and state, independent output controls, carrier fields, modulation, feedback, then Apply. Dividers separate these functional regions. Connection settings occupy a shallower full-width panel.

### State and segmented controls

Output On/Off and modulation Off/AM/FM use explicit pressed states. Output On gains a soft green fill; active modulation gains a white fill and accent text. Unknown output uses warning text. Draft feedback says “Unapplied changes”; completed states distinguish “Simulated settings” from “Commands accepted.” Errors appear in readable red-tinted alerts.

**The Separate Actions Rule.** Applying parameters and switching an output are separate actions. Dirty drafts disable Output On; Output Off stays available while connected and idle.

Clean editors follow the local API command cache; refresh preserves dirty drafts. Cache values must not be described as hardware measurements. A persistent mode notice identifies simulation or the limitations of LAN command state.

### Navigation

The slim resource navigation contains API documentation and a Quick guide disclosure. Activity is another disclosure below the controls. Hover underlines links; keyboard focus uses the shared outline. A focusable skip link leads directly to channel controls.

## Do's and Don'ts

### Do:

- **Do** keep both channels equally prominent and independently actionable.
- **Do** retain explicit units and written states at every viewport width.
- **Do** preserve unsent drafts when updating connection or cached command state.
- **Do** stack quantity fields on narrow screens instead of compressing their contents.

### Don't:

- **Don't** represent simulated or accepted commands as measured hardware state.
- **Don't** combine Apply with Output On.
- **Don't** use color alone to communicate selection, failure, or unknown state.

Not canonized: the one-off (11px) accepted-summary size and decorative monogram geometry are local details, not defaults for new controls or branding.
