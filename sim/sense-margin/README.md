# sense-margin

Sense-path margin bench: the committed `efuse_sense` subcircuit (with `efuse_comp`),
extracted at run time from `design/efuse_otp_array.spice`, against a resistor standing
in for the selected fuse.

```sh
sim/sense-margin/run.sh --dry-run   # validates the request set with `klt sim --dry-run`; runs no corner
sim/sense-margin/run.sh             # submits the grid to the batch fleet; writes a record
```

## What it measures

Eight `klt sim` requests, submitted together with `klt sim --batch-set` (batch only; a
failed submit exits non-zero and is never re-run locally), each over the decision-0005
grid: 5 process (`typical`, `ff`, `ss`, `fs`, `sf`) x -40/25/125 C x vdd33 2.97/3.30/3.63 V
(45 corners per request).

| Request | Fuse | Reference |
|---|---|---|
| `bench_rf140/200/260_rr400` | intact, 140 / 200 / 260 ohm (A4) | 400 ohm (A6) |
| `bench_rf630/900/open_rr400` | programmed, 630 / 900 ohm / open (1 Gohm) (A5) | 400 ohm |
| `control_rf140/260_rr200` | intact | 200 ohm: negative control |

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
wrong side at 200 ohm (`negative_control.demonstrates_bench_can_fail`).

## Assumptions (all flagged in each record)

- A4 intact 140-260 ohm and A5 programmed >= 630 ohm / open: only the 200 ohm and 900 ohm
  points are documented; the ranges around them are assumptions.
- A6 reference 400 ohm (decision 0003).
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
