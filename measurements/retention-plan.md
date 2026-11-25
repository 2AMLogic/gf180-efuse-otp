# Retention and re-connection plan

Status: **plan only for retention (R1). Nothing about drift has been measured, and no
silicon exists.** It adds an item the spec does not cover: the spec's "Cannot
show" list names "read-disturb or post-program drift" (`spec/efuse-otp.md`
section 3) and `grep -ri "retention\|reconnect"` over `spec/`, `measurements/`,
`sim/*/README.md` and `README.md` found no hit before this file (2026-11-25).
This file edits no ratified spec row (A1-A6 are unchanged).

## Background and its limits

Cooker, Dellar et al., *An Investigation into the Physics of Blowing
Polysilicon Fuses*, 62nd European Study Group with Industry, Limerick 2008
(<https://miis.maths.ox.ac.uk/201/1/analog-1.pdf>). A workshop report, not
peer-reviewed, on a WSi/poly dog-bone fuse (1.5 um x 0.35 um neck) from a
different process. Per the issue text it reports **needle growth across blown
fuses after 1000 h at 125 C under sustained bias** (its section 4.3), a possible
path to re-connection. That is a reference shape, not a gf180 value: no
re-connection rate, resistance, time or temperature for gf180's Poly2 fuse
follows from it. (The section number is as quoted in the issue; the PDF was not
re-read here.)

## Item R1: high-temperature biased retention (silicon only, not simulated)

| Field | Plan |
|---|---|
| What | Programmed fuses held at elevated temperature under sustained bias, read back at intervals; track each fuse's programmed resistance and read decision over time |
| Stress point | 125 C and 1000 h, taken from the report's observation. **Assumption**: no gf180 source for the stress conditions. 125 C is also the upper temperature in decision 0005 |
| Bias | Sustained bias across the programmed fuse at the read level. The exact level is **not documented** (spec 1.2: read-disturb limit not documented) and is to be chosen at test time and recorded |
| Readout | Resistance of each programmed fuse at each read point, plus the sense-path decision, so drift is seen before the bit flips |
| Why not simulated | No compact model simulates the fuse changing state, and the PDK model is a two-value switch (`pblow`). Needle growth is not representable (spec section 3). Simulation can only say what the sense path does for an assumed drifted resistance, covered below |
| Pass criterion | None invented here. This is a measurement item, not a ratified bound; a criterion needs a decision record that cites a source |
| Status | `not measured`; no owner issue yet |

## How the sense-margin assumptions cover drift

Re-connection would lower a programmed fuse's resistance over life. The sense
path trips on the fuse versus the 400 ohm reference (A6, decision 0003), so the
question is how far a programmed fuse can fall before it reads as intact.

- **Covered by committed records.** The A5 lower edge is 630 ohm
  (900 ohm minus 30 %, an assumption). At 630 ohm all 45 corners read the
  correct side. Latest sense-margin record
  (`sim/sense-margin/records/20261123T140330Z-f6eeac7/record.json`, committed
  physical `ppolyf_u` `XRb`/`XRref`): minimum signed margin at 630 ohm is
  0.0253 V against the ideal 400 ohm stand-in and 0.0210 V against the
  physical `XRref` (`ss`, 125 C, 2.97 V). So a drift from the documented 900 ohm
  down to 630 ohm is covered, by assumption A5. A8 applies: fs/sf keep the
  typical resistor sheet rho.
- **Break-even is measured.** A programmed-resistance sweep (300 to 540 ohm in
  40 ohm steps, 45 corners per point, batch) is committed at
  `sim/sense-breakeven/records/20261125T093522Z-f6eeac7/record.json`. The
  zero-margin resistance, interpolated between swept points:
  - against the ideal 400 ohm reference: 400.69 to 400.72 ohm across all 45
    corners (spread 0.03 ohm);
  - against the committed physical `XRref`: **327.91 ohm (`ff`, 125 C, 3.63 V)
    to 471.99 ohm (`ss`, -40 C, 2.97 V)**, a 144 ohm spread. A programmed fuse
    that drifted below about 472 ohm can read as intact at the worst corner.
    Between 472 and 630 ohm the bit reads correctly at every corner, so the A5
    edge keeps about 158 ohm of headroom, outside A5 only below 630 ohm. The
    interpolation interval is 40 ohm; it is still an interpolation of a
    nonlinear quantity, but it now rests on a committed sweep.
- **What it does not cover.** The bench fuse is an ideal resistor behind a
  switch. Reference tolerance and offset are covered only at the 630 ohm and
  260 ohm edges by Monte Carlo
  (`sim/sense-mc/records/20261123T140937Z-f6eeac7/record.json`: 0 of 540
  failing for both the ideal 400 ohm and the physical `XRref` nominals;
  physical-reference minimum analog margin 17.1 mV at 630 ohm and 3.9 mV at
  260 ohm; A7/A8 noted), which uses an assumed reference-tolerance sigma. None
  of it says a real fuse drifts to any of these values, or how fast; that is
  what R1 would measure. Any A5 change would need a decision record; none is
  proposed here.

## Related questions, recorded without design

- **Multi-pulse or weak-pulse programming** (many weaker pulses blowing a fuse
  cumulatively): open, unmeasured. The report does not test it, and its
  melt-then-pinch mechanism suggests sub-melt pulses do little. No sequencer,
  simulation or controller change is proposed; it is not designed for unless
  measured.
- **Margin for a partly programmed fuse** (a pulse that does not fully blow):
  the same 400 to 630 ohm region applies, with the same estimate-only status.
