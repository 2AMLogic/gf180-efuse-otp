# layout

### Digital partition

Routed layout of the digital partition (`efuse_otp_ctrl`), produced by
`klt place-and-route` from the mapped netlist `rtl/efuse_otp_ctrl.gl.v`. The
analog partition is below.

| File | Role |
|---|---|
| `pnr-request.json` | The `klt place-and-route` request: `gf180mcu_fd_sc_mcu7t5v0`, 40 % utilization, 10 µm core margin, PDN by platform recipe (`power.preset: gf180mcu_7t_6M`; see DRC below), `power.tapcell.distance_um` 15, I/O pins on Metal3 (horizontal) / Metal2 (vertical), `target_stage: route`, seed 1, `portable_paths`. The straps and connects were spelled out by hand until #154, for klt 0.8.0, whose preset emitted `-split_cuts {Metal3 0.128}`; the pinned 0.9.0 preset carries `split_cuts: null`, so the hand copy was redundant. `power.preset` and explicit `power.straps` are mutually exclusive, which is why the override had to be a full copy rather than a patch. |
| `pnr.sh` | Runs the flow with the pinned klt (`signoff/klt-pin.txt`), refuses to write anything unless the response is `status: ok`, `stage_reached: route`, `power.pdn: true` with `route_drc_violation_count` and `antenna_violation_count` both 0, and writes the files below. `--check` runs `klt place-and-route --check` plus the GDS sha256; `--check --rerun` re-runs the flow and diffs the verdict-bearing fields. |
| `pnr-report.json` | Committed `--format json` response. Route stage reached, 0 route DRC and 0 antenna violations, `power.pdn: true`, `power.preset: gf180mcu_7t_6M`, `power.connects_overridden: false`, `power.connects[].split_cuts: null`, `power.tapcell_master: gf180mcu_fd_sc_mcu7t5v0__filltie`, `power.placed.tapcells: 171`. |
| `efuse_otp_ctrl.gds` | Routed GDS (standard-cell GDS views merged in by klt). Its sha256 is in `efuse_otp_ctrl.gds.sha256`. |
| `efuse_otp_ctrl.asbuilt.v` | `verilog_path` output: the as-built gate-level netlist (CTS buffers, resizes, antenna diodes included). This, not `rtl/efuse_otp_ctrl.gl.v`, is the reference for the controller LVS run. |
| `attest.sh` | Writes both T1 item 2 envelopes with the pinned klt's own producer, `klt signoff --attest 2 --input <stream>`: `pnr.attest.json` (digital) and `../signoff/item2-analog.attest.json` (analog). `--check` re-attests and fails (exit 3) if either committed envelope has drifted. The digital regeneration claim is a geometry digest, read from `klt stats --format json`'s `geometry_digest`; every field is the producer's. |
| `pnr.attest.json` | The T1 item 2 (digital) envelope: `klt signoff --attest 2` bound to the routed GDS (readable, non-empty top cell, dbu on grid), with a `layout/pnr.sh` regeneration claim (geometry digest, so GDS write times do not matter). |
| `lvs.sh` | Runs `klt lvs` with the pinned klt (`signoff/klt-pin.txt`) on `efuse_otp_ctrl.gds` against `efuse_otp_ctrl.asbuilt.v` and keeps the JSON report as found. `--check` re-hashes the stream, the netlist and the deck against the committed report (`--rerun` re-runs the compare). The gate-level reference resolves each standard cell's pin order from the library's own spice/cdl under `<PDK_ROOT>/gf180mcuD/libs.ref` (`PDK_ROOT`, default `~/.ciel`, passed to klt as `reference.pdk_root`), so CI (which installs no PDK) cannot run it. |
| `lvs-ctrl.report.json` | Committed `--format json` LVS report (T1 item 4, digital): `status: match`, `power_connectivity.status: match` — see "LVS" below. |

## Reproduce

```sh
layout/pnr.sh --check            # cheap: input netlist and deck hashes, GDS sha256
layout/pnr.sh --check --rerun    # full: re-runs OpenROAD (about 2 minutes)
layout/pnr.sh && layout/attest.sh   # regenerate, then re-attest (both item 2 envelopes)
layout/attest.sh --check         # exit 3 = an item 2 envelope has drifted (CI runs this)
layout/lvs.sh --check            # LVS report input hashes current (exit 3 = drifted)
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
netlist `design/efuse_otp_array.spice`. Three cells are routed and LVS-matched:
`efuse_ls`, `efuse_rowdrv` and `efuse_coldrv` (see "efuse_ls routing" and
"efuse_rowdrv / efuse_coldrv routing" below). Every other cell is
placement-only: `efuse_sense`, `efuse_comp`, and everything that contains a
fuse (`efuse_bitcell`, `efuse_row`, the array top).

| File | Role |
|---|---|
| `gen_efuse_otp.py` | Generator. Reads the netlist; one cell per subcircuit, named as the subcircuit. MOS devices come from `klt gen mos_array` at the netlist W and L; the fuse is the PDK primitive. `efuse_ls` is placed on a stated two-row floorplan and routed with generator-drawn geometry; `efuse_rowdrv` and `efuse_coldrv` are routed from it and the leaf devices the same way. |
| `regen-gds.sh` | Reproduce the files below with the pinned klt (`signoff/klt-pin.txt`) and PDK (`sim/pdk.json`); `--check` exits 3 on drift. Two runs produce byte-identical streams (the routing is drawn from netlist-derived constants and the generators' own reported port positions — no randomness). |
| `efuse_otp_array.gds` | The committed stream. Top cell `efuse_otp_array`. |
| `efuse_otp_array.gds.sha256` | sha256 of the stream (below). |
| `efuse_otp_array.report.json` | Every device cell with its model, W, L and fingers, the array pitch and bounding box, and the `routed` block naming the three routed cells and their routing planes. `efuse_coldrv__Mdrv` carries `m: 3` (drawn as three placed units). |
| `drc-ls.report.json` | Committed `klt drc` report of the routed `efuse_ls` cell (top `efuse_ls` of this stream), written by `layout/drc.sh`; `status: clean` under the same curated deck as the partition reports (see "DRC" below). |
| `drc-rowdrv.report.json`, `drc-coldrv.report.json` | The same for the routed `efuse_rowdrv` and `efuse_coldrv` cells (tops of this stream); `status: clean`. |
| `lvs-rowdrv.report.json`, `lvs-coldrv.report.json` | Committed `klt lvs` reports of the routed `efuse_rowdrv` and `efuse_coldrv` cells against their `.subckt`s, written by `layout/lvs.sh`; both `status: match` — see "efuse_rowdrv / efuse_coldrv LVS" below. |
| `lvs-ls.report.json` | Committed `klt lvs` report of the routed `efuse_ls` cell against its `.subckt` in `design/efuse_otp_array.spice`, written by `layout/lvs.sh`; `status: match` — see "efuse_ls LVS" below. |

```sh
layout/regen-gds.sh           # rewrite the files
layout/regen-gds.sh --check   # exit 3 = drifted
layout/drc.sh                 # rewrite curated DRC for five tops and native DRC for the two partitions
layout/lvs.sh                 # rewrite the LVS reports (lvs-ctrl needs the PDK; the analog parts do not)
layout/attest.sh              # re-attest afterwards (writes ../signoff/item2-analog.attest.json)
```

`sha256(efuse_otp_array.gds)` = `2cd9b515e8688c64fd9c844769eb43d5bdbc3aaa31da92dd1a480693bc117fa4`
(klt 0.9.2, `gf180mcuC` at open_pdks `f6eeac7`; the stream after the via2 Metal3-enclosure
fix: every M3 end that lands a via2 cut — the six marked `LS_W3N` strip ends in `efuse_ls`
and every lane end in `efuse_coldrv` — reaches 0.06 µm past the cut edge, closing the
native deck's V2.4b and V2.4c findings while all lane widths, positions and spacings
are unchanged). The previous hash
`133922ed156c68534147da03101307feff268163c732b4b3c3cbf997b6293b98` was the
stream after the via2-landing fix: via2
cuts with no M3 above them were dropped, and pin-level via2 is cut only where an M2 pad exists.
The previous hash `4cf5b69431e9523935b18eb4d04ef5227884bf5d885ff20bde165628dfa9ec7f` was the
stream the `efuse_rowdrv` / `efuse_coldrv` routing produced (#273), still carrying the unlanded
via2; before it
`bf79985e4a0a15aaad4eeb56d8bbbb9652a9dd5de1c8bda8ddbebed56a36a0dc` was the stream with only
`efuse_ls` routed; before that `a48866157cd4753e17e112eab70e1e39128ee1c0085e3d311d890a6aaee8fafc` was the
placed-only stream at the same pin (itself a re-run of the 0.8.0 stream
`186be6b6e0ba5200154a20b6e66bda85b629aea378d76b6e683918dd0d412224`, byte-different
only in GDS record order — klayout-tools#5499 stopped writing KLayout's
`$$$CONTEXT_INFO$$$` structure; streams carry no write time, so the check is a
byte compare). The stream changed at 133922ed because the via2 cuts that had
no M3 (or no M2) landing were removed, and at 2cd9b515 because the M3
enclosure at every landed cut end was extended to the V2.4b/V2.4c minimum;
`layout/check_via2_landing.sh` and the native report gate these in CI.

## efuse_ls routing

`efuse_ls` (the program-path level shifter, 6 MOS, no fuse) is routed by
`gen_efuse_otp.py` (`ls_cell`) — the one cell in the analog stream that is a
circuit rather than a placement.

- **Floorplan (stated).** Two device rows: NMOS at y = 0 (`XMni` x = 0,
  `XMn1` x = 6.24, `XMn2` x = 12.90), PMOS at y = 12.0 (`XMpi`, `XMp1`,
  `XMp2` at the same column origins). The 3.3 V input inverter
  (`XMpi`/`XMni`) holds column 0; the cross-coupled 6 V latch inverters hold
  columns 1 and 2 — each voltage family stays in one row, and within a column
  a device's source, drain and gate pads land near-vertically aligned.
- **Planes.** M1 carries the device pads and the guard-ring taps (all `klt
  gen` ports are M1). M2 carries everything horizontal: the `vss` rail below
  the NMOS row, the `vprog` wire joining the two 6 V PMOS rings across the
  channel top, and per-net channel runs. M3 carries everything vertical:
  one stub per connected pad. Via1/via2 are the deck's fixed 0.26 µm squares
  on 0.4 µm M2 landing pads.
- **Supplies tie through the rings.** Every source pad is merged into its own
  guard ring with an M1 bridge (source and body are one net per device), and
  each ring leaves the island at one tap: `TAP_S` for the NMOS row and the 6 V
  PMOS pair, `TAP_W` for `XMpi` (`vdd33` exits west; it has a single
  connection, so it needs no rail).
- **What is connected.** All 7 nets of the `.subckt`: `in`, `inb`, `x1`,
  `out`, `vdd33`, `vprog`, `vss` — including the internal `inb`/`x1`, so the
  extracted cell's net names are the netlist's (each net also carries a text
  label on the Metal1 label layer 34/10, which is how `klt lvs` anchors the
  five `.subckt` pins by name below).
- **`gen-compose` is not used.** Re-probed at the pin before committing to
  hand-drawn routing (klayout-tools 0.9.2, two-row floorplan, per-net planes,
  via-drop routing): the same 4 of 7 nets the #73 note measured on 0.8.0
  (`inb`, `vss`, `vdd33`, `vprog`) still come back unrouted ("crosses
  already-routed net"), so every net here is drawn by the generator instead.

## efuse_ls LVS (first analog compare at the pinned klt)

`layout/lvs.sh`'s `ls` part extracts `efuse_ls` from this stream (layout top
`efuse_ls`, curated `gf180mcu` deck) and compares it against the `.subckt
efuse_ls` block of `design/efuse_otp_array.spice`. The reference is in
simulation form (X cards calling the PDK device subcircuits), so the request
sets `reference.form: "subckt-call"` for klt's automatic conversion; no PDK
or library install is needed (unlike the `ctrl` part). The report is
`layout/lvs-ls.report.json`:

**`status: match`**, with the five `.subckt` pins (`in out vdd33 vprog vss`)
anchored by name (`options.anchor_top_level_pins: true`) — which is what
settles the cross-coupled latch's two-fold automorphism: `XMn1`/`XMp1` and
`XMn2`/`XMp2` are device-for-device interchangeable, so `x1` and `out` could
pair swapped on topology alone. The three report entries are warnings-only
(the subckt-call conversion's `bjt`/`RES` classes with no devices on either
side, and the pin-anchoring note itself); none affects the verdict. What the
`match` reaches is the same pin-to-net correctness as the digital run below —
not rail continuity or current capability.

## efuse_rowdrv / efuse_coldrv routing

Both cells are drawn by `gen_efuse_otp.py` (`rowdrv_cell`, `coldrv_cell`), not
by `gen-compose` (the `efuse_ls` section above records why).

**`efuse_rowdrv`** is one `efuse_ls` instance (18.26 × 19.92 µm) at the cell
origin with the five ports landed as M1 labels on the instance's own pads
(`row_sel` = `in`, `wl` = `out`, `vdd33`, `vprog`, `vss`); there is nothing
else to draw.

**`efuse_coldrv`** (131.64 × 29.55 µm): `efuse_ls` at the origin and the twelve
MOS devices in one row east of it, in netlist order (`Mppa Mppb Mnpa Mnpb`,
three `Mdrv` units, `Mpra Mprb Mnra Mnrb Mpr Mnr Mrs`), 2 µm between bounding
boxes. All 13 nets are drawn:

- **`Mdrv` as `m=3`.** `leaf()` still reads only `W` and `L`; `coldrv_cell`
  reads the instance's `m` and places that many copies of the one `Mdrv` leaf
  cell (each the 10-finger 100 µm unit), so the layout carries 3 × 100 µm in
  parallel like the reference's `m=3` expansion. Their S, G and D are tied by
  the routing below (`bl`, `pg`, `vprog`). `efuse_otp_array.report.json` lists
  `efuse_coldrv__Mdrv` once, with `"m": 3`.
- **Signals.** Every non-supply pin gets via1, a 0.4 µm M2 pad and via2, then a
  vertical M3 lane up to its net's M2 track in a channel above `efuse_ls`'s
  top (0.72 µm track pitch). A device's S lane sits 0.16 µm west of its pin,
  G on it, D 0.16 µm east, so the three lanes are 0.59 µm apart (0.30 µm M3,
  0.29 µm space). M3 meets M2 only at a net's own via2. Nets with one pin
  (`sbl`) need no track and get no via2 either (nothing would land on it; the
  net stays reachable through its M1 label and M2 pad).
- **Supplies.** A source on its body net (all the supply-source devices) is
  merged into its guard ring with the same M1 bridge as `ls_cell`; each ring
  leaves at `TAP_S`, down an M3 lane to its supply's M2 rail below the row
  (`vss` y = −1.5 µm, shared with `efuse_ls`'s own rail; `vdd33` −2.22;
  `vprog` −2.94). Sources off their body (`Mnpa`, `Mnra`, `Mrs`: `mp`, `mr`,
  `sbl`) are signals; their rings still tap `vss`.
- **Entering `efuse_ls` without touching its internals.** `in` by an M3 run
  west off the existing `in` vertical, then up; `out` by an M3 run east off the
  `out` vertical at its drop above `XMp2.D`, then up; `vdd33` at the west end
  of its M2 stub (via2, M3 down); `vprog` by extending its M2 run east (via2,
  M3 down); `vss` by extending its rail east. `efuse_ls` itself changed
  only by dropping its five unlanded D-pad via2 cuts (see the gate below).
- **Via2 landing gate.** via2 rules `V2.3c`, `V2.3d`, `V2.4b` and `V2.4c` are
  unmodeled in the deck, and `metal3.enclosing.via2.1` / `metal2.enclosing.via2.1`
  pass a via2 with no M3 over it or no M2 under it (and LVS cannot see a dead
  cut), so neither DRC nor LVS can catch an unlanded via2.
  `layout/check_via2_landing.sh` counts, per cell, via2 shapes with no merged M3
  above them and via2 shapes with no merged M2 below them (exit 1 on any of
  either); it reports 0 for both in `efuse_ls`, `efuse_rowdrv`, `efuse_coldrv`
  and the top. Before the fix the M3-above counts were 5, 5, 6 and 208 (the
  D-pad cuts in `_ls_pad3` and `sbl`'s lane cut in `_stack`); an interim
  version that cut at every `net_pins` entry left 2 / 16 with no M2 below in
  `efuse_coldrv` / the top (the two `efuse_ls` M3-to-M3 tie-ins), which the
  one-sided gate did not see. `net_pins` now records whether a pin has an M2
  pad and only those get a pin-level cut. A cell's via2 is judged against the
  metal in that cell's own hierarchy. CI runs the gate on both committed streams,
  the array and `layout/efuse_otp_ctrl.gds` (pass the ctrl stream as the argument);
  as of 2026-11-18 the ctrl stream reports 0 / 0 in each of its three via2-bearing
  cells (`VIA_Via2_VH` of 1, `VIA_via2_3_8960_1200_1_5_1040_1040` of 5,
  `efuse_otp_ctrl` of 1429).

## efuse_rowdrv / efuse_coldrv LVS

`layout/lvs.sh`'s `rowdrv` and `coldrv` parts extract each cell from this
stream and compare it with its `.subckt` in `design/efuse_otp_array.spice`
(`reference.form: "subckt-call"`, `anchor_top_level_pins: true`, as `ls`).
Two options beyond `ls`, both klt's documented ones:

- `options.flatten_reference: ["<top>"]` — **`efuse_ls` is compared as its six
  devices, not as a hierarchical instance.** klt's layout extraction is flat,
  so the layout side has one circuit while the reference has `EFUSE_LS` as a
  subcircuit; with no option the compare answers "circuit could not be
  matched" and its hint names this option. Flattening the reference under the
  top (the list keeps only the top circuit) is the supported way, and the
  report discloses it (`topology.flattened`). The `efuse_ls` boundary is
  therefore not separately asserted here; `lvs-ls` is the check of that cell.
- `options.combine_devices: true` — the extractor otherwise reports each of
  the 30 `Mdrv` fingers as its own W = 10 µm device against the reference's
  three W = 100 µm copies. Combining merges
  parallel devices on both sides, so the layout's three units and the
  reference's `m=3` copies meet as one W = 300 µm device.

| Cell | status | nets (layout / ref / matched) | devices | warnings |
|---|---|---|---|---|
| `efuse_rowdrv` | **`match`** | 7 / 7 / 7 | 6 / 6 / 6 | 4 (`bjt`/`RES` no-device classes, flatten, pin anchoring) |
| `efuse_coldrv` | **`match`** | 16 / 16 / 16 | 18 / 18 / 18 | 4 (same) |

(18 devices = the 11 single MOS, the combined `Mdrv`, and `efuse_ls`'s six.)
As with `ls`, `match` is pin-to-net correctness of the placed wires, not rail
continuity or current capability: nothing here says the 300 µm `Mdrv` and its
rails carry the programming current (that is the simulated program-path
claim, not a layout one).

## What is in the stream

- Hierarchy: `efuse_otp_array` (32 × 8) contains `efuse_row` (an array of 32),
  `efuse_rowdrv` (array of 32), `efuse_coldrv` (array of 8) and `efuse_sense`;
  `efuse_row` is an array of 8 `efuse_bitcell`; `efuse_rowdrv` and `efuse_coldrv`
  contain `efuse_ls`; `efuse_sense` contains `efuse_comp`. Leaf device cells are
  named `<subcircuit>__<instance>`.
- **`efuse_ls`, `efuse_rowdrv` and `efuse_coldrv` are routed** (the exceptions
  to the placement-only caveat below): `efuse_ls`'s six devices sit on a stated
  two-row floorplan and all 7 nets are generator-drawn on M1/M2/M3 with
  via1/via2 stacks — see "efuse_ls routing" above; `efuse_rowdrv` is one routed
  `efuse_ls` and `efuse_coldrv` draws all 13 nets — see "efuse_rowdrv /
  efuse_coldrv routing". Everything else (`efuse_sense`, `efuse_comp`,
  `efuse_bitcell`, `efuse_row` and the array top) is placement-only: devices
  and cells are placed; no wire joins them.
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

## DRC (T1 item 3)

### PDK-native results

Both partitions fail the full foundry deck. The array passes **all 27**
`EF.*` checks on fuse geometry. The controller draws neither PLFUSE (125/5)
nor EFUSE_MK (80/5). T1 item 3 stays uncited for both partitions.

| Stream | Native report | Checked categories | `EF.*` markers | All markers |
|---|---|---:|---:|---:|
| Array | [drc-array.native.report.json](drc-array.native.report.json) | 772 | 0 | 53 |
| Controller | [drc-ctrl.native.report.json](drc-ctrl.native.report.json) | 772 | 0 | 9 |

`layout/drc.sh` uses the Ciel revision in `sim/pdk.json` (`f6eeac7`,
`CIEL_ROOT` defaults to `~/.ciel`). The array takes `gf180mcuC` from its
generator pin, the controller takes `gf180mcuD` from its place-and-route
report. Both select five metal levels and MIM option B. C selects 9K top
metal and D selects 11K. The controller's PDK layer map puts Metal5 on
81/0. Each run passes the corresponding `variant` to the PDK main script
`tech/drc/gf180mcu.drc`, with `decks=all` (including metal slotting) and
`threads=1`. These measurements used pinned klt 0.9.2 and standalone
KLayout 0.30.12 (minimum 0.30.9).

For each variant, an empty-layout `--list-rule-categories` run independently
declared 763 categories. The script requires the 27 foundry IDs in that
set of expectations and adds any finding-producing categories from a first
pass over the stream. For both streams those extra categories are DBU and
the eight density rules below. The final run uses klt's exact-name coverage
assertion. Both reports record `coverage_assertion.satisfied: true`, all 27
IDs in `coverage.rules_checked`, and zero `EF.*` markers. The native list
includes EF.14, EF.17 and EF.20 in addition to the 24 IDs the curated deck
lists as unmodeled.

| Finding | Array | Controller | Follow-up |
|---|---:|---:|---|
| Metal3 enclosure of via2 (V2.4b, V2.4c) | 0 | 0 | fixed ([#308](https://github.com/2AMLogic/gf180-efuse-otp/issues/308)): every M3 end landing a via2 reaches 0.06 µm past the cut edge |
| PMOS (DF.4d_MV, DV.6, PL.2_MV) and resistor geometry (PP.9, PRES.5, PRES.6, SB.13) | 44 | 0 | [Generated device cores #309](https://github.com/2AMLogic/gf180-efuse-otp/issues/309) |
| Global density (DCF.1b, PL.8, M1.4 through M5.4, MT.3) | 8 | 8 | [Density #310](https://github.com/2AMLogic/gf180-efuse-otp/issues/310) |
| DBU (0.0005 µm, required 0.001 µm) | 1 | 1 | [Partition writers #311](https://github.com/2AMLogic/gf180-efuse-otp/issues/311), [klt generator default #5721](https://github.com/2AMLogic/klayout-tools/issues/5721) |

`layout/drc.sh --check` verifies the input and deck hashes.
`layout/drc.sh --check --rerun` replays the native invocation, including
the variant and coverage assertion, and compares the complete report.
The script binds the pinned PDK to the relative `pdk/` path recorded by
klt in a temporary directory so both operations work across installations.

The committed native reports use `--engine klayout`. In a scratch manifest,
pinned klt read them and graded both rows `check_failed`. A separate
`--engine both` run returned `comparison.state: not_comparable`, and the
same grader returned `unrecognized_envelope` for that report shape.
[Comparison issue #5720](https://github.com/2AMLogic/klayout-tools/issues/5720)
and [grader fix #5815](https://github.com/2AMLogic/klayout-tools/issues/5815).

### Curated results

`layout/drc.sh` runs `klt drc --deck gf180mcu --top <top>` (the pinned klt,
`signoff/klt-pin.txt`) on each GDS — both partitions, plus the routed
`efuse_ls`, `efuse_rowdrv` and `efuse_coldrv` cells as tops of the analog
stream — and keeps the reports as found: `layout/drc-array.report.json`,
`layout/drc-ctrl.report.json`, `layout/drc-ls.report.json`,
`layout/drc-rowdrv.report.json`, `layout/drc-coldrv.report.json`. `--check` re-hashes
the input and the deck against them (`--rerun` re-runs). Deck content hash,
all runs: `sha256:c3f2cce49000857a3a71cb65203aabf0eb27cd0ee6b1c60e29792355c455c4b1`
(klt 0.9.2, klayout 0.30.13 — the pin; re-run under it 2026-11-17, all three
clean as before). The 0.9.0 deck hash was
`sha256:cf44de63f0a5b01c1d09c4d58e0535e990aa4b070bcaae17fd3a94a67a1d97e1`
(klayout 0.30.13; #154 re-ran both partitions under it).
That hash is engine-dependent and `signoff/klt-pin.txt` does not constrain the
klayout engine, so a future install of the same pin can resolve a different
engine and make `layout/drc.sh --check` report `drifted` with nothing else
changed (klayout-tools#5601). CI does not run `drc.sh --check`, so this is a
local-reproducibility caveat, not a CI gate.
Both partitions and all three routed cells are clean under the curated deck.

| Partition | status | violations |
|---|---|---|
| analog `efuse_otp_array` | `clean` | 0 (was 2560 `*.ongrid.1` hits at `45987b9`) |
| digital `efuse_otp_ctrl` | `clean` | 0 (was 2525 before the two request changes below) |
| routed `efuse_ls` cell | `clean` | 0 (first run with routing; this issue) |
| routed `efuse_rowdrv` / `efuse_coldrv` cells | `clean` | 0 / 0 (first run; the analog partition stays 0 on the regenerated stream) |

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
  curated deck's coverage below, which models no `EF.*` rule — though the pinned
  deck does check seven eFuse-layer rules of its own on this partition, five of
  them new at klt 0.9.0 (below).
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
  1. **PDN via stack.** Stated as history: the klt 0.8.0 `gf180mcu_7t_6M` preset
     connected Metal1 to Metal4 with `-split_cuts {Metal3 0.128}`. Replacing that
     preset with the same straps and connects minus `split_cuts` removed every
     `metal2/3/4.ongrid.1`, `via2/3.ongrid.1` and `via2/3.width.1` hit (2022 in
     total), including the 666 (24 + 426 + 108 + 108) attributed to foundry cells: those
     polygons were the foundry cells' shapes overlaid by the oversized cuts, not
     defects of the cells. Measured: the re-run, same seed, has 0 such hits. This is
     klayout-tools#4301 gap 1; no new tool issue is needed. That gap closed upstream on
     2026-10-27, so the pinned klt 0.9.0 preset carries `split_cuts: null` on the same
     Metal1→Metal4 connect and the hand-written block became redundant: #154 restored
     `power.preset: gf180mcu_7t_6M` in `layout/pnr-request.json`, and the stream it
     produces is byte-identical to the hand-written form's (same GDS sha256, same 20
     generated OpenROAD Tcl scripts). The 0 hits above are therefore unchanged by that
     restoration.
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
| `rules_checked` | 55 rules | 72 rules |
| `layers_in_stream_without_rules` | `34/10` | `0/0`, `21/10`, `34/10`, `36/10`, `63/63`, `81/10`, `204/10` |
| `rules_skipped` | 71 rules; the eFuse-layer rules `efuse_mk.enclosing.lvs_source.1`, `efuse_mk.ongrid.1`, `efuse_mk.space.1`, `plfuse.ongrid.1`, `plfuse.separation.comp.1`, `plfuse.separation.nplus.1`, `plfuse.separation.sab.1` are **checked**; `plfuse.separation.esd.1` and `plfuse.separation.resistor.1` are skipped | 54 rules, including all nine eFuse-layer rules (the digital partition draws no `PLFUSE`/`EFUSE_MK`) |
| `deck_scope` | both: 10.4.2 MIM Option B, 10.7 DRC_BJT Mark Layer, 7.12 Contact, 7.13 Metaln, 7.14 Vian, 7.15 MetalTop, 7.4 Nwell, 7.5 Comp, 7.7 Poly2, 7.8 Nplus, 7.9 Pplus, 9.1 Bond Pad, EF, ESD, GR, MDN, MDP, OFFGRID, SB | |

**No foundry `EF.*` rule is modelled, but the pinned deck is no longer blind to
the eFuse layers.** Two facts, measured from the reports under the pin and worth
keeping apart:

- Neither report's `coverage.rules_checked` carries a rule named `EF.*`, and both
  reports list every one of `EF.01`, `EF.02`, `EF.03`, `EF.04a`–`EF.04d`, `EF.05`–
  `EF.13`, `EF.15`, `EF.16a`/`EF.16b`, `EF.18`, `EF.19`, `EF.21`, `EF.22a`/`EF.22b`
  (24 rules) under `coverage.unmodeled_rules`. The exact-value `EF.*` set is still
  not run (klayout-tools#4312).
- The pinned klt 0.9.0 deck did gain an `EF` entry in `coverage.deck_scope` and
  now checks five eFuse-layer rules on the analog partition that klt 0.8.0 did
  not: `efuse_mk.enclosing.lvs_source.1`, `efuse_mk.space.1`,
  `plfuse.separation.comp.1`, `plfuse.separation.nplus.1` and
  `plfuse.separation.sab.1` (on top of the two `*.ongrid.1` rules 0.8.0 already
  ran). `efuse_otp_array` is clean under all seven. Two more,
  `plfuse.separation.esd.1` and `plfuse.separation.resistor.1`, remain skipped.
  These are klt's own layer-named rules, not the foundry's `EF.*` IDs, and no
  mapping between the two is published — so they are additional coverage, not
  evidence for any `EF.*` row.

## LVS (T1 item 4, digital): the routed controller matches its as-built netlist

`layout/lvs.sh` runs `klt lvs` (the pinned klt, `signoff/klt-pin.txt`) on
`layout/efuse_otp_ctrl.gds` — extracted inline under the curated `gf180mcu`
deck — against `layout/efuse_otp_ctrl.asbuilt.v` (`reference.form:
"gate-level-verilog"`, `reference.library: gf180mcu_fd_sc_mcu7t5v0`) and keeps
the report as found: `layout/lvs-ctrl.report.json`. It needs the PDK.
The script header and `signoff/README.md` ("Re-run the
controller LVS") say why and how the root is pinned.

Verdict, klt 0.9.2 (deck content hash
`sha256:c3f2cce49000857a3a71cb65203aabf0eb27cd0ee6b1c60e29792355c455c4b1`,
klayout engine 0.30.13 — the same engine-dependence caveat as DRC above;
re-run at the 0.9.2 pin 2026-11-17, `match`/`match` as before, the report's
`schema_version` moved 2 → 3 with additive fields):
**`status: match` and `power_connectivity.status: match`**, `error_count: 0`.
It is cited for `4.digital` in `signoff/block-manifest.json` and the record
reads `met`. Digests, both recorded in the report: layout
`sha256:574c94b191ddb5592f230aa6cfb32bcde5f1ee8c1707d820c3bce5c73bb4f21a` —
the report's `provenance.input.content_hash`, equal to
`efuse_otp_ctrl.gds.sha256`; reference
`sha256:921a3d477c8b10a67554b086d478bcd9a360b1a961fcd3c893bcde01c9da1628` —
`environment.reference_sha256`, `sha256 efuse_otp_ctrl.asbuilt.v`.

How the compare is shaped (this is not the extraction's default):

- The request sets `layout.abstract_cells: gf180mcu_fd_sc_mcu7t5v0__*`, so
  every standard cell extracts as a pin-only black box instead of flattening
  to its transistors, matching the gate-level reference's granularity. Pins
  resolved from the cells' own label text (`resolution_source:
  in_cell_labels`, no LEF needed). Without it the extraction is
  transistor-level and the compare is a measured hierarchy mismatch (3106
  layout devices vs 0 reference, `status: mismatch`,
  `topology.hierarchy_mismatch`) — the un-abstracted request is the wrong
  shape for this reference, not a finding about the stream.
- The power/ground half runs (`power_connectivity` is on by default for this
  reference form; `unchecked` would mean it never asked): `expected_nets`
  maps the library's four PG pins (`VDD VNW VPW VSS`, the `.SUBCKT` pin order)
  onto the PDN's two rails (`power_net: VDD`, `ground_net: VSS` in
  `pnr-report.json`). Result: 1421 instances checked, 0 findings, derivation
  `declared-by-every-instantiated-master` corroborated across all 34
  instantiated masters — but only half the mapping produced evidence: the
  report's `power_pins` is `["VDD", "VSS"]` and its `unchecked_expected_pins`
  is `["VNW", "VPW"]`. The abstracted cells resolve 4 of the library's 6
  `.SUBCKT` pins from their in-cell labels (`VNW`/`VPW` carry none), and the
  circuits that would carry the well connections (`filltie`, `endcap`,
  `fill_*`) are power-only-pruned before the compare (warning below), so
  those two keys matched zero checkable rows and produced no findings and no
  evidence — a key that resolves no pin is indistinguishable, in
  `finding_count`, from one checked and found correct, which is exactly what
  `unchecked_expected_pins` exists to disambiguate. The tap mapping is
  therefore an asserted intent, not a checked result: it is declared so a
  well-tap disagreement *would* render as a finding, but no instance pin
  resolved on either `VNW` or `VPW`, so their correspondence
  (`VNW`→`VDD`, `VPW`→`VSS`) is not evidence this run provides.
  `body_verification: verified` with `device_count: 0`
  — every cell was abstracted, so there were no extracted devices to
  body-verify; the verdict covers the instances' pin correspondence, not the
  cells' transistor-level internals (which are the foundry library's, not
  this stream's).
- **What the check reaches** (T1 item 4's own caveat, restated so the
  `match` cannot be over-read): per-standard-cell-instance *pin-to-net*
  correctness on the extracted stream. It is **not** geometric rail or grid
  continuity — whether a rail is unbroken, or carries the current, is
  `klt ring-check`/`klt power` and the DRC deck's business, and nothing here
  claims it.

Warnings-only mismatches, listed with the claim as item 4 requires (all
`severity: warning`, none affects the verdict): 36 × `topology` "nets were
paired ambiguously; the comparer resolved it structurally"; 1 ×
`topology.power_only_pruned` (layout-side power-only circuits — the tap
cells, which the gate-level reference never instantiates — removed before
the compare; those are also the circuits that would have carried the well
connections, which is why `VNW`/`VPW` appear under `unchecked_expected_pins`
in the power bullet above); 1 × `topology.top_level_pins_anchored` (the 57 top-level pin
names declared on both sides anchored by name first).

## What is not claimed

- **No routing outside `efuse_ls`, `efuse_rowdrv` and `efuse_coldrv` in the
  analog stream.** Those three are routed (above) and LVS-match their
  `.subckt`s; every other analog cell is placement-only — devices and cells
  placed, no wire joining them — so beyond those boundaries
  `efuse_otp_array.gds` is still not a circuit: `efuse_sense`, `efuse_comp`
  and everything that contains a fuse (`efuse_bitcell`, `efuse_row`, the array
  top) remain unrouted. The array top does not yet connect the drivers to the
  array. The digital stream is the
  opposite case: it is routed, and its per-instance connectivity is the LVS
  run above.
- **Analog LVS reaches the three routed cells only.** The LVS sections above
  cover item 4's digital half (`lvs-ctrl`) and the routed `efuse_ls`,
  `efuse_rowdrv` and `efuse_coldrv` cells (`lvs-ls`, `lvs-rowdrv`,
  `lvs-coldrv`); the last two compare `efuse_ls` flattened, not as an
  instance;
  item 4's analog partition as a whole still needs the fuse as a device
  (#32), and ERC is #33 — no analog LVS row is claimed. DRC status is not
  restated here: the `DRC (T1 item 3)` section above is the one place it is
  reported. Whatever it reports is clean only under the curated deck's
  coverage — `klt drc` does not run the `EF.*` rules at all
  (`spec/efuse-otp.md` §1.3) — so T1 item 3 stays `unmet` and no envelope is
  cited for it.
- Cell-to-cell clearance is a fixed 2 µm between bounding boxes, not a
  rule-derived spacing.
- **The item 2 envelopes claim the stream, not the circuit.** Both are written by
  `klt signoff --attest 2`, whose checks are the stream's readability, a
  non-empty top cell and an on-grid database unit, plus the attester's
  regeneration claim (generator and hash, never run by the grader). The
  producer's `summary` is fixed text and says nothing about the content: for
  `efuse_otp_array.gds` the claim is **placed hierarchy with `efuse_ls`,
  `efuse_rowdrv` and `efuse_coldrv` routed — no DRC, LVS or connectivity
  statement beyond them**, and neither
  envelope makes one for either partition.
