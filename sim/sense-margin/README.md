# sense-margin

Sense-path margin bench: the committed `efuse_sense` subcircuit (with `efuse_comp`),
extracted at run time from `design/efuse_otp_array.spice`, against a resistor standing
in for the selected fuse.

```sh
sim/sense-margin/run.sh --dry-run   # validates the request set with `klt sim --dry-run`; runs no corner
sim/sense-margin/run.sh             # submits the grid to the batch fleet; writes a record
```

## What it measures

Fourteen `klt sim` requests, submitted together with `klt sim --batch-set` (batch only; a
failed submit exits non-zero and is never re-run locally), each over the decision-0005
grid: 5 process (`typical`, `ff`, `ss`, `fs`, `sf`) x -40/25/125 C x vdd33 2.97/3.30/3.63 V
(45 corners per request).

| Request | Fuse | Reference |
|---|---|---|
| `bench_rf140/200/260_rr400` | intact, 140 / 200 / 260 ohm (A4) | 400 ohm (A6) |
| `bench_rf630/900/open_rr400` | programmed, 630 / 900 ohm / open (1 Gohm) (A5) | 400 ohm |
| `control_rf140/260_rr200` | intact | 200 ohm: negative control |
| `phys_rf<each fuse value>_rrphys` | the six fuse values above | the committed `XRref` (`ppolyf_u`, 0.8 µm x 1.05 µm) left in the deck, so its terminal resistance and corner dependence are exercised; recorded under `physical_reference` and counted in the headline verdicts (`--physical-reference`) |

`summarize.py` is told which requests `run.sh` submitted (`--rfuse-intact`,
`--rfuse-programmed`, `--rfuse-control` with `--rref`/`--rref-control`) and opens all
expected reports by name rather than discovering whatever arrived. A request whose report
is missing, or that came back carrying no corners, exits 4 and **writes no record** —
a partial set is not evidence, the same rule `sim/program-select` and `sim/sense-mc`
apply to their own sets. Reports that are all present but have points without values
are still recorded for diagnosis, with `complete: false` and exit 3.

One clock edge at 15 ns; `sense_en` is held asserted. Read just before the edge:
`v_sbl`, `v_sref`. Read after it: `v_sense_out`, `v_cp`, `v_cn`.

Per point `summarize.py` writes into `record.json`: the analog margin
`v(sbl) - v(sref)` (sign-flipped for intact so positive is always the correct side),
whether the comparator resolved (`|v(cp) - v(cn)| >= 0.5 vdd33`), the latched decision bit
and whether it matches the expected bit. The binding (minimum-margin) corner is named per
fuse value. **Pass/fail is data in the record, not an exit status.**

Each request also declares a `klt sim` limit `margin_v >= 0` (signed, so positive is the
correct side of the reference; measured just before the edge), so the pinned grader can
grade the reports. The negative control carries the same limit and its 260 ohm request
reads fail. Reference tolerance and offset are not covered by corners (see `sim/sense-mc/`).

The negative control moves the reference inside the intact range. It demonstrates the
bench can fail when some intact point that reads the correct side at 400 ohm reads the
wrong side at 200 ohm (`negative_control.demonstrates_bench_can_fail`). Both control
requests are named in the expected set, so that flag is never asserted over part of the
control set: if either report is absent the run is refused rather than recorded.

## Assumptions (all flagged in each record)

- A4 intact 140-260 ohm and A5 programmed >= 630 ohm / open: only the 200 ohm and 900 ohm
  points are documented; the ranges around them are assumptions.
- A6 reference 400 ohm (decision 0003).
- **A8, new, not in the spec: fs/sf resistor corners hold the typical sheet rho.** The pinned PDK
  model library declares `res_typical`, `res_ss` and `res_ff` but no `res_fs`/`res_sf`, so the
  bias and reference resistors (`XRb`, and `XRref` in the `phys_*` requests) keep the typical sheet
  rho at those two corners. Holding it there has no documented source, and it bounds what the
  physical-reference requests can claim about corner dependence at fs/sf.
- The fuse leg is the fuse resistor behind a series switch and select device matching the
  reference leg's (`nfet_06v0` 4u / 60u). No bitline capacitance, no column-mux leakage.
- Program supply held at 5.0 V; it only gates the 6 V select devices here.
- Not simulated: reference tolerance and comparator offset (the spec's sense-margin row
  includes both). Neither has a documented source; Monte Carlo is tracked separately.

## Record

`records/<UTC stamp>-<pdk rev:7>/` holds the generated decks and requests, `sets/` (the
`klt sim` reports, with the batch job ids in `environment.remote`), `set-report.json`,
`klt.err` and `record.json`. `run.sh` refuses to reuse a directory; committed records are
never edited. The PDK revision is the pin in `sim/pdk.json`; `run.sh` refuses any other
tree and checks that the gf180mcuD files the fleet reads are byte-identical to the pinned
gf180mcuC ones.

## Re-run against the physical ppolyf_u resistors (issue 321)

PR #323 replaced both ideal resistors in `efuse_sense` with PDK `ppolyf_u` devices (`XRb`,
`XRref`) and pointed this bench's `phys_*` requests at the committed reference. New record:
`records/20261123T140330Z-f6eeac7/record.json` -- fourteen requests (six ideal-400-ohm
`bench_rf*_rr400`, six physical-`XRref` `phys_rf*_rrphys`, two negative controls) over the
45 decision-0005 corners each, 14 batch jobs in `remote_job_ids`, `res_ss` for ss,
`res_ff` for ff, `res_typical` for typical/fs/sf (A8). Comparison baseline:
`records/20261109T002043Z-f6eeac7`.

- Ideal-reference minimum signed margins: 28.8 / 22.2 / 15.5 mV (intact 140/200/260 ohm) and
  25.3 / 55.1 mV / 2.70 V (programmed 630/900/open), all binding at ss / 125 C / 2.97 V
  (open at sf / 125 C / 2.97 V) -- the baseline read 29.6 / 22.8 / 16.0, 26.0 / 56.6 mV /
  2.70 V at the same corners, so the real `XRb` moves the ideal-reference margins by well
  under a millivolt.
- Physical-`XRref` minimum signed margins: 29.7 / 20.5 / **10.9 mV** (intact; binding at
  fs or ff / 125 C / 2.97 V) and 21.0 / 50.7 mV / 2.70 V (programmed; ss / 125 C / 2.97 V,
  open at sf). The intact edge loses about 4.7 mV of margin against the ideal stand-in
  (10.9 vs 15.5 mV at 260 ohm): the `ppolyf_u` reference's terminal resistance and corner
  dependence, which the stand-in hid, now sit in the measured evidence.
- Comparator resolution and decision correctness hold everywhere: no unresolved point, the
  latched bit matches the expected bit at all 45 corners for every fuse value, under both
  the ideal and the physical reference (`decision_correct_everywhere` true).
- Negative control: the 200-ohm reference flips all 45 intact points to the wrong side
  (`demonstrates_bench_can_fail` true, 45 flipped points), as in the baseline.

The campaign completes with no failing corner; the intact-edge physical margin (10.9 mV) is
the number a further sense-path sizing question would start from. No circuit resize and no
spec change is made here.
