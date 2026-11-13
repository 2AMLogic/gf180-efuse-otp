# layout

### Digital partition

Routed layout of the digital partition (`efuse_otp_ctrl`), produced by
`klt place-and-route` from the mapped netlist `rtl/efuse_otp_ctrl.gl.v`. The
analog partition is below.

| File | Role |
|---|---|
| `pnr-request.json` | The `klt place-and-route` request: `gf180mcu_fd_sc_mcu7t5v0`, 40 % utilization, 10 µm core margin, explicit PDN straps and connects (the `gf180mcu_7t_6M` recipe values, written out because a preset cannot be combined with overrides, with the `split_cuts` option dropped; see DRC below), `power.tapcell.distance_um` 15, I/O pins on Metal3 (horizontal) / Metal2 (vertical), `target_stage: route`, seed 1, `portable_paths`. |
| `pnr.sh` | Runs the flow with the pinned klt (`signoff/klt-pin.txt`), asserts `status: ok` and `power.pdn: true`, and writes the files below. `--check` runs `klt place-and-route --check` plus the GDS sha256; `--check --rerun` re-runs the flow and diffs the verdict-bearing fields. |
| `pnr-report.json` | Committed `--format json` response. Route stage reached, 0 route DRC and 0 antenna violations, `power.pdn: true`, `power.connects[].split_cuts: null`, `power.tapcell_master: gf180mcu_fd_sc_mcu7t5v0__filltie`. |
| `efuse_otp_ctrl.gds` | Routed GDS (standard-cell GDS views merged in by klt). Its sha256 is in `efuse_otp_ctrl.gds.sha256`. |
| `efuse_otp_ctrl.asbuilt.v` | `verilog_path` output: the as-built gate-level netlist (CTS buffers, resizes, antenna diodes included). This, not `rtl/efuse_otp_ctrl.gl.v`, is the reference for the controller LVS run. |
| `attest.sh`, `pnr.attest.json` | The T1 item 2 (digital) attestation: a generic envelope bound to the GDS, with a `layout/pnr.sh` regeneration claim (geometry digest). klt has no `--attest 2`, so `attest.sh` assembles it from the committed report (klayout-tools issues #4188, #4221). |

## Reproduce

```sh
layout/pnr.sh --check            # cheap: input netlist and deck hashes, GDS sha256
layout/pnr.sh --check --rerun    # full: re-runs OpenROAD (about 2 minutes)
layout/pnr.sh && layout/attest.sh   # regenerate, then re-attest
```

Needs `openroad` on `PATH` and the gf180mcuD PDK (`PDK_ROOT`, default `~/.ciel`).
`layout/.klt/` is scratch and is gitignored.

## Assumptions

- **Clock period 100 ns** (`constraints.clock_period_ns`) is a P&R target chosen
  to drive CTS and timing-driven steps, not a requirement from the spec: the spec
  states no clock frequency. The `worst_slack_ns` in the report is against this
  assumed period, so it is not evidence of a timing margin (STA is a separate
  item).
- Utilization, core margin, I/O layers and seed are floorplan choices, not spec
  values.
- Only the typical-corner liberty is used for the P&R timing figures; the
  report's `corners` are not a PVT sign-off.

### Analog partition

Analog-partition layout (T1 item 2): `efuse_otp_array.gds`, generated from the
netlist `design/efuse_otp_array.spice`.

| File | Role |
|---|---|
| `gen_efuse_otp.py` | Generator. Reads the netlist; one cell per subcircuit, named as the subcircuit. MOS devices come from `klt gen mos_array` at the netlist W and L; the fuse is the PDK primitive. |
| `regen-gds.sh` | Reproduce the files below with the pinned klt (`signoff/klt-pin.txt`) and PDK (`sim/pdk.json`); `--check` exits 3 on drift. |
| `efuse_otp_array.gds` | The committed stream. Top cell `efuse_otp_array`. |
| `efuse_otp_array.gds.sha256` | sha256 of the stream (below). |
| `efuse_otp_array.report.json` | Every device cell with its model, W, L and fingers, the array pitch and bounding box. |

```sh
layout/regen-gds.sh           # rewrite the files
layout/regen-gds.sh --check   # exit 3 = drifted
```

`sha256(efuse_otp_array.gds)` = `186be6b6e0ba5200154a20b6e66bda85b629aea378d76b6e683918dd0d412224`
(klt 0.8.0, `gf180mcuC` at open_pdks `f6eeac7`). Streams carry no write time, so
the check is a byte compare.

## What is in the stream

- Hierarchy: `efuse_otp_array` (32 × 8) contains `efuse_row` (an array of 32),
  `efuse_rowdrv` (array of 32), `efuse_coldrv` (array of 8) and `efuse_sense`;
  `efuse_row` is an array of 8 `efuse_bitcell`; `efuse_rowdrv` and `efuse_coldrv`
  contain `efuse_ls`; `efuse_sense` contains `efuse_comp`. Leaf device cells are
  named `<subcircuit>__<instance>`.
- Array pitch follows the wider of the bitcell and column driver (x) and the
  taller of the bitcell and row driver (y), so word lines and bit lines line up
  with their drivers.
- **Fuse**: the PDK `efuse_cell` from `libs.ref/gf180mcu_fd_pr/gds/efuse.gds`,
  copied without modification (only the database unit is rescaled by the exact
  integer 2). `gen_efuse_otp.py` compares it with the PDK stream, per layer and
  flattened, on every run and exits 4 on any difference, so the geometry the
  `EF.02` (0.18 µm), `EF.03` (1.26 µm) and `EF.21` (5.53 µm) values describe
  is the PDK's by construction. This is a geometry-equality check, not an
  `EF.*` rule run. `klt gen --list-pdk-pcells` finds no PCell library for this
  PDK (klayout-tools#4247), so the stream is read directly.
- **Select device**: `nfet_06v0`, W = 60 µm, L = 0.7 µm, drawn as 6 fingers of
  10 µm (same total W; the netlist has `nf=1`). Wide devices are folded into
  fingers of at most 10 µm the same way (e.g. the 100 µm column driver).
- Other device sizes are the netlist's placeholders (`design/README.md`,
  2026-10-27); the layout carries that caveat.
- Resistors: the schematic uses ideal resistors, so the layout draws
  `ppolyf_u` strips 1 µm wide, with length from the model library's
  `rsh_ppolyf_u` = 350 Ω/sq, snapped to the 0.005 µm grid. The 1 µm width is an assumption, not a sourced
  value.

## DRC (T1 item 3): both partitions clean, `EF.*` not evaluated

`layout/drc.sh` runs `klt drc --deck gf180mcu --top <top>` (the pinned klt,
`signoff/klt-pin.txt`) on each GDS and keeps the reports as found:
`layout/drc-array.report.json`, `layout/drc-ctrl.report.json`. `--check` re-hashes
the input and the deck against them (`--rerun` re-runs). Deck content hash, both
runs: `sha256:0eb6df1bafc5106ec50bd58479dbd7cda36bb685f1ef18cd3a2244a6e7e48666`
(klt 0.8.0, klayout 0.30.12). **Item 3 stays `unmet` (`EF.*` is not evaluated, see below); no envelope is cited for it.** Both partitions are clean under the curated deck.

| Partition | status | violations |
|---|---|---|
| analog `efuse_otp_array` | `clean` | 0 (was 2560 `*.ongrid.1` hits at `45987b9`) |
| digital `efuse_otp_ctrl` | `clean` | 0 (was 2525 before the two request changes below) |

Sources (from the reports' `source_cell`):

- **Analog:** the 2560 `*.ongrid.1` hits were all in the MOS cells and had two
  causes in `layout/gen_efuse_otp.py`: the placed bbox lower-left sat on the
  0.0005 µm database grid, finer than the 0.005 µm rule grid, so it is now
  snapped to the rule grid (rounded away from the neighbour, so the 2 µm gap is
  never reduced; array pitches rounded up). Snapping the translation instead
  would be wrong: the PDK fuse stream is itself 0.001 µm off the grid in y, so
  its bbox, not its origin, is what is landed on the grid. The two `ppolyf_u`
  strips had lengths (5.714, 1.143 µm) off the grid; they are now snapped to
  0.005 µm, so the drawn resistance differs slightly from the netlist value
  (`ohms_drawn` in `efuse_otp_array.report.json`; the 350 Ω/sq and 1 µm width
  remain assumptions). The fuse cell's geometry is unchanged
  (`verify_fuse` against the PDK stream passes). Clean means clean under the
  curated deck's coverage below, which has no `EF.*` rules.
- **Digital, classification of the 2525 hits before the fix** (sum 2525; counts
  from the previous `layout/drc-ctrl.report.json`, `source_cell` of the hit):

  | Rule | Total | PDN via cells (`VIA_*`) | Foundry cells (`gf180mcu_fd_sc_mcu7t5v0__*`) | Other |
  |---|---|---|---|---|
  | `metal2.ongrid.1` | 444 | 18 (`VIA_via4_5_8960_8960_*`) | 426 | 0 |
  | `metal3.ongrid.1` | 444 | 444 (`VIA_via2_3_8960_1200_*`) | 0 | 0 |
  | `metal4.ongrid.1` | 24 | 0 | 24 | 0 |
  | `via2.ongrid.1` | 444 | 444 (`VIA_via2_3_8960_1200_*`) | 0 | 0 |
  | `via3.ongrid.1` | 444 | 444 (`VIA_via2_3_8960_1200_*`) | 0 | 0 |
  | `via2.width.1` | 111 | 3 (`VIA_via4_5_*`) | 108 | 0 |
  | `via3.width.1` | 111 | 3 (`VIA_via4_5_*`) | 108 | 0 |
  | `comp.tap_distance.nwell.mv.1` | 253 | 0 | 253 | 0 |
  | `comp.tap_distance.psub.mv.1` | 250 | 0 | 250 | 0 |

  `source_cell` names the cell whose geometry the polygon sits in, not the cause.
  Two causes in our request account for all 2525:
  1. **PDN via stack.** The `gf180mcu_7t_6M` preset connects Metal1 to Metal4 with
     `-split_cuts {Metal3 0.128}`. Replacing the preset with the same straps and
     connects minus `split_cuts` (`layout/pnr-request.json`) removed every
     `metal2/3/4.ongrid.1`, `via2/3.ongrid.1` and `via2/3.width.1` hit (2022 in
     total), including the 666 (24 + 426 + 108 + 108) attributed to foundry cells: those
     polygons were the foundry cells' shapes overlaid by the oversized cuts, not
     defects of the cells. Measured: the re-run, same seed, has 0 such hits. This is
     klayout-tools#4301 gap 1; no new tool issue is needed.
  2. **Tap cell pitch.** The tap-distance rules (15 µm, 5V/6V) are about the tap
     cells' placement. The default pitch is 100 µm, so 503 hits. With
     `power.tapcell.distance_um: 15` (171 tap cells instead of 19) both
     `comp.tap_distance.*.mv.1` rules report 0.

  Re-run result: `status: clean`, 0 violations; `pnr-report.json` still has 0
  route DRC and 0 antenna violations. Placement changed (more tap cells), so
  `efuse_otp_ctrl.asbuilt.v` differs from before in clock-tree buffer naming and
  the clock-load cells; `rtl/efuse_otp_ctrl.gl.v` is unchanged.

  No foundry-cell DRC status is cited and none is needed: no hit remains in a
  foundry cell. That the foundry cells' own geometry is DRC-clean under this deck
  rests on this run only (the deck's curated scope, `coverage` below); it is not
  taken from foundry documentation. The generated GDS was not hand-edited.

Coverage, quoted from the reports (`coverage.*`):

| | analog | digital |
|---|---|---|
| `layers_in_stream_without_rules` | `34/10`, `100/8` | `0/0`, `21/10`, `34/10`, `36/10`, `63/63`, `81/10`, `204/10` |
| `rules_skipped` | 64 rules, none `EF.*`; `efuse_mk.ongrid.1`/`plfuse.ongrid.1` are checked | 42 rules, including `efuse_mk.ongrid.1`, `plfuse.ongrid.1` |
| `deck_scope` | both: 10.4.2 MIM Option B, 10.7 DRC_BJT Mark Layer, 7.12 Contact, 7.13 Metaln, 7.14 Vian, 7.15 MetalTop, 7.4 Nwell, 7.5 Comp, 7.7 Poly2, 7.8 Nplus, 7.9 Pplus, 9.1 Bond Pad, ESD, GR, OFFGRID, SB | |

**`EF.*` rules are not evaluated.** Neither report's `coverage.rules_checked`
carries an `EF.*` rule: the curated deck has none (klayout-tools#4312). The route
via the PDK's own `efuse.rb` also fails: `klt drc --engine klayout --deck-file
<PDK>/libs.tech/klayout/tech/drc/rule_decks/efuse.rb` exits 1 with
`NameError: uninitialized constant GF180_DRC_REGISTRY` (the file is one fragment
of a deck that must be assembled with the registry; klayout-tools#4002). The spec
row "DRC clean including every `EF.*` rule" stays `unmet`.

## What is not claimed

- **No routing and no connectivity.** Devices and cells are placed; no wire
  joins them, so the stream is not a circuit and does not match the netlist
  until routing is added.
- **No LVS, no ERC.** Those are #32 and #33. DRC status is not restated here:
  the `DRC (T1 item 3)` section above is the one place it is reported. Whatever
  it reports is clean only under the curated deck's coverage — `klt drc` does
  not run the `EF.*` rules at all (`spec/efuse-otp.md` §1.3) — so T1 item 3
  stays `unmet` and no envelope is cited for it.
- Cell-to-cell clearance is a fixed 2 µm between bounding boxes, not a
  rule-derived spacing.
- The `item2-analog.attest.json` envelope is hand-written: `klt signoff
  --attest` has no producer for item 2 (klayout-tools#4188, #4221).
