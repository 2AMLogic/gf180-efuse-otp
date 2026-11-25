# Retention and re-connection plan

Status: **plan only. Nothing here has been measured or simulated, and no
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
  correct side; minimum signed margin is 0.0260 V at `ss`, 125 C, 2.97 V
  (`sim/sense-margin/records/20261109T002043Z-f6eeac7/record.json`,
  `fuses["630"]`). So a drift from the documented 900 ohm down to 630 ohm is
  covered, by assumption A5.
- **Break-even is bracketed by records, not recorded.** The 260 ohm intact
  point (minimum signed margin 0.0160 V) and the 630 ohm programmed point read
  on opposite sides of the reference at every corner of the same record. So the
  zero-margin resistance lies between 260 and 630 ohm at every corner. No
  committed record holds a point inside that interval, so no record gives the
  break-even value itself.
- **Estimate, not a record.** Linearly interpolating `margin_v`
  (`v(sbl) - v(sref)`) between the 260 and 630 ohm points of that record puts
  the zero crossing at 400.7 to 400.8 ohm across all 45 corners, i.e. at the
  400 ohm reference (what a current comparison against a resistor reference
  should give). It is a two-point interpolation of a nonlinear quantity and is
  only an estimate. A programmed fuse that drifted below roughly 400 ohm would
  be expected to read as intact; between about 400 and 630 ohm the bit is
  expected to read correctly but lies outside A5 and has no record.
- **What it does not cover.** The bench fuse is an ideal resistor behind a
  switch. Reference tolerance and offset are covered only at the 630 ohm and
  260 ohm edges by `sim/sense-mc/` (Monte Carlo, 0 failing of 540 each), which
  uses an assumed reference-tolerance sigma. None of it says a real fuse drifts
  to any of these values, or how fast; that is what R1 would measure.
- **Not done here.** A direct break-even needs a sense-margin run over a
  programmed-resistance sweep through `klt sim` (batch, `--wait-for-capacity
  600`) with a new append-only record under `sim/`. That is a follow-up, not
  part of this plan; any A5 change would need a decision record.

## Related questions, recorded without design

- **Multi-pulse or weak-pulse programming** (many weaker pulses blowing a fuse
  cumulatively): open, unmeasured. The report does not test it, and its
  melt-then-pinch mechanism suggests sub-melt pulses do little. No sequencer,
  simulation or controller change is proposed; it is not designed for unless
  measured.
- **Margin for a partly programmed fuse** (a pulse that does not fully blow):
  the same 400 to 630 ohm region applies, with the same estimate-only status.
