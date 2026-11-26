# sim

Analog simulation (xschem + ngspice) under a pinned gf180mcu PDK.

## Pin

`sim/pdk.json` is the single record of the toolchain: open_pdks revision
`f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, ciel 2.6.1, variant `gf180mcuC`
(its `sm141064.ngspice` carries the 3.3 V and 6 V MOS families), ngspice and
xschem versions. `sim/lib/pdk_env.sh` resolves the variant directory under
`${CIEL_ROOT:-$HOME/.ciel}` and exits non-zero unless the tree's `SOURCES`
file reads exactly `open_pdks <pin>`. A tree at another revision (for example a
leftover `~/.volare`) is never used. Every simulation record names the PDK
revision it ran under.

`sim/lib/` also holds the boilerplate the benches share rather than copy:
`pdk_env.sh` for the `bench_*` shell helpers each `run.sh` sources, and
`bench_record.py` for the record-provenance fields each `summarize.py` writes
(the pinned/simulated variant statement, the timestamp and tool versions, the
backend and remote job ids, and the `record.json` writer). The variant
statement is built from the file list `pdk_fleet_check` actually compares, so
it cannot go stale against the check it describes. The simulator version
(`engine_versions`) is collected from the `environment.engine_version` of the
reports in the record, not probed on the submitting host: these campaigns are
batch only, so the host's own `ngspice` runs no corner. It is a sorted list, so
a set whose corners ran on more than one engine version stays visible.
`summarize.py` runs under `python3 -I`, so it imports the module through an
explicit `sys.path` insert.

## Cold start

```bash
# 1. Install ciel 2.6.1 and the pinned PDK (once per machine)
pip install "ciel==2.6.1"          # or: uvx --from "ciel==2.6.1" ciel ...
ciel enable --pdk-family gf180mcu -l gf180mcu_fd_pr f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7
# 2. ngspice (any 4x release for the smoke run) and jq must be on PATH
# 3. Resolver self-test (match / wrong revision / no tree)
sim/lib/test_pdk_env.sh
# 4. Smoke simulation: writes a new record under sim/pdk-smoke/records/
sim/pdk-smoke/run.sh
```

`run.sh` runs one single-corner (typical, 27 °C) DC operating point and Id-Vgs
sweep for one NMOS and one PMOS of each of the 3.3 V and 6 V families. It only
shows that the models load and converge; it selects and sizes nothing.

## Records

Each run creates `sim/pdk-smoke/records/<UTC stamp>-<rev>/` holding
`netlist.cir` (the deck as run), `smoke.log`, and `record.json` (PDK revision,
variant, corner, temperature, ngspice version, and a per-device `converged`
flag derived from the log). Records are append-only: `run.sh` refuses to reuse
an existing directory, and committed records are never edited.

## Program-select width sweep

`sim/program-select/run.sh` sweeps the `nfet_06v0` select width over the full
decision-0005 PVT set with the fuse at 140/200/260 Ω. It writes
`sim/program-select/records/<stamp>-<rev>/record.json` (every PVT point, fuse
current, Vgs, Vds, pass/fail against 10 mA, binding corner per width). The grid
is 15 `klt sim` requests submitted with `--batch-set`, so it needs the batch
fleet; a failed submit is reported and never re-run locally.
The swept deck is [`program-select/cell.cir.in`](program-select/cell.cir.in); the
cell as designed (the implemented 60 µm bitcell) is
[`../design/efuse_bitcell.sch`](../design/efuse_bitcell.sch). Result and
derivation: `design/README.md`.

## Program-current corner verification

`sim/corner-verification/run.sh` drives the committed program path (`efuse_coldrv`,
`efuse_rowdrv`, each with its `efuse_ls` level shifter, and `efuse_bitcell`, extracted from
`design/efuse_otp_array.spice`) into one selected cell, replacing the ideal gate drive of the
width sweep. Fuse 140/200/260 ohm, decision-0005 grid (5 process x -40/25/125 C x supplies
that step together: vdd33 2.97/3.30/3.63 V with vprog 4.5/5.0/5.5 V), plus a negative control
(select narrowed to 4 um). Four `klt sim` requests, `--batch-set` (batch only; a failed submit
is reported and never re-run locally); `--dry-run` validates the set and leaves no record.
It writes `sim/corner-verification/records/<stamp>-<rev>/record.json` (per-point current,
per-fuse pass/fail against 10 mA, binding corner, negative-control validity). The sense row
is not re-run: `record.json` quotes the committed `sim/sense-margin` record by reference.

Result (record `20261108T235928Z-f6eeac7`, after the column driver `Mdrv` went from W = 100 um
to 3 x 100 um, option (a) of the 2026-11-08 operator ruling): all 45 corners pass at each fuse
value (135 points over the three fuse values); binding corner ss / 125 C / vdd33 2.97 V / vprog
4.5 V / 260 ohm at 10.97 mA (>= 10 mA, A2); negative control reads fail. The earlier record
`20261030T230649Z-f6eeac7` (8.835 mA at the same corner, 100 um driver) and the failed first
attempt `20261108T235750Z-f6eeac7` (single 300 um device, outside the `pfet_06v0` model bin of
W <= 100 um, so all 45 corners errored in ngspice) are kept as append-only evidence. The fuse
range and the 20 ohm route are assumptions (A4, no documented source).

## Sense-margin bench

`sim/sense-margin/run.sh` runs the committed sense path (`efuse_sense`, `efuse_comp`)
against intact 140/200/260 ohm (A4) and programmed 630/900 ohm/open (A5) fuse values and
the 400 ohm reference (A6) over the decision-0005 grid, plus a negative control with the
reference moved inside the intact range. It submits 14 requests with `klt sim --batch-set`
(batch only; six against the ideal 400 ohm stand-in, six against the committed physical
`XRref`) and writes `sim/sense-margin/records/<stamp>-<rev>/record.json`. Assumptions
and the record layout: `sim/sense-margin/README.md`.

## Routed sense-cell PEX (#61)

The published KLT 0.9.2 report in `layout/pex-sense.report.json` extracts
the physical `efuse_sense` cell from the delivered array. Its 33 devices
include the PDK bias and reference resistors. The seven-port fixture models
the selected fuse and series switches outside the cell. It holds VPROG at
5 V, samples the signed margin at 14.9 ns and checks the latched bit at 38 ns
after the 15 ns clock edge. All 270 schematic, 270 device-only and 270
RC-extracted decisions pass. KLT reports biased bodies and zero unbiased
devices. Use ngspice 42 and the PDK revision in `sim/pdk.json`.

```sh
python3 sim/post-layout-sense.py
python3 sim/post-layout-sense.py --controls
uv run --no-project --with klayout==0.30.14 python3 sim/post-layout-sense.py --geometry-control
```

The generator extends the existing CN Metal2 track 36 µm west at a width
of 0.42 µm. The load to substrate changes from 13.515993 to 16.138599 fF
at CN and from 16.297548 to 16.296276 fF at CP. A 1 Ω substrate tie
preserves the corrected outcomes at all nine SS/630 Ω conditions. Restoring
only CN capacitance to its previous value in scratch reproduces all nine
wrong bits across the 270-point sweep. The geometry control removes the
actual extension and regenerates fill. It reproduces the pre-repair GDS
byte-for-byte and exits 3 on nine wrong programmed reads. At −40 °C and
2.97 V the margin is +13.7037 mV in both layouts, while the post-edge
CP−CN changes from −2.8557 V before the repair to +2.8582 V after it.
The three commands leave the physical streams, decks, simulator logs and
native control report in `layout/.klt/sense-pex/`.

## Full-array read and program path trial (#61)

`layout/pex-array-fuse-candidate.report.json` measures row 31, column 0 of
the actual 47-port array. Source-pinned KLT revision `25da22a11805` and
KLayout 0.30.14 recognize 256 fuse links, 2,393 raw extracted devices and
485 nets. Released KLT 0.9.2 recognizes zero fuse devices at this top.
The schematic leg restores the original xschem top header. The extracted
leg uses the fuse at (955.99, 683.06) µm and changes only that element's test
resistance. The other 255 links retain their nominal resistance.

Each leg runs 270 transient reads (five process corners, three temperatures,
three logic voltages, six fuse resistances), 135 program operating points
(the same corner grid with three intact resistances), and two address
controls. VPROG is 5 V for reads. Program supplies step together at
2.97/4.5 V, 3.30/5.0 V and 3.63/5.5 V per decision 0005. The original
physical reference and column mux, all bitline loading, row driver and
column driver participate. The spec assumptions for the resistive fuse
states and mixed-corner resistor models still apply.

| Full coupled bench | Schematic | Extracted |
| --- | --- | --- |
| Correct read at 38 ns | 250/270 | 251/270 |
| Correct pre-edge margin sign | 270/270 | 270/270 |
| Resolved latch at 38 ns | 270/270 | 270/270 |
| Program current ≥10 mA | 135/135 | 135/135 |
| Minimum selected program current | 11.3487 mA | 11.0436 mA |

On the adopted stream, every incorrect read is a 630 Ω programmed fuse.

| Process | Schematic wrong | Extracted wrong |
| --- | ---: | ---: |
| typical | 4 | 4 |
| ss | 6 | 6 |
| ff | 1 | 2 |
| fs | 7 | 3 |
| sf | 2 | 4 |

The two previously demonstrated full-array errors (SS/−40 °C/2.97 V and
TT/25 °C/3.30 V at 630 Ω) now read correctly; the separate full-grid report
exposes the remaining combinations. At the binding SS/125 °C, 2.97/4.5 V
and 260 Ω program point, selecting row 30 or column 1 leaves only 83 pA or
183 pA in the original measured fuse, respectively. KLT uses lumped-star
interconnect resistance here. `layout/program-current.json` independently
replays finite contacts, sheet resistance and all 256 sites at the binding
corner. Its refined far-cell minimum is 10.6532 mA nominal, 10.0955 mA
high, or 10.0296 mA with the selected PMOS bodies on VPROG and the NMOS
body on ground at the high corner.

```sh
python3 sim/post-layout-array.py
python3 sim/post-layout-array.py --full-grid
# After post-layout-sense.py --geometry-control recreates the pre-repair stream:
python3 sim/post-layout-array.py --geometry-control
python3 sim/post-layout-array.py --geometry-control --full-grid
```

The short test passes 17 measurement rows on the delivered layout. The
full grid exits 3 and writes the native 947-row report to
`layout/.klt/array-pex/baseline-full/pex.report.json`. On the reconstructed
previous GDS, every one of the 45 extracted 630 Ω reads fails. The adopted
route recovers 26 of those 45. The other 225 intact, nominal programmed and
open cases still read correctly. Both programming grids and address controls
pass. All 947 schematic values and decisions agree between the two runs.
The native 947-row pre-repair report is archived in
`sim/array-pex/metal-control.report.json`. Both full-array layouts have
biased bodies and zero unbiased devices.
The circuit correction is tracked in [#430](https://github.com/2AMLogic/gf180-efuse-otp/issues/430).
Item 7 analog remains uncited pending a passing coupled read suite and a
published fuse-capable extractor. The P06 current results concern static
delivery; they do not estimate the programming pulse heating or fuse yield.

## Controller post-route SDF status

T1 item 7 (digital) wants the controller functional suite re-run on the routed
gate-level netlist with back-annotated SDF timing, cited from a
`klt functional-verification` report whose `environment.sdf.annotated` is
`true`. **No such report exists yet: at the pinned klt (`signoff/klt-pin.txt`,
0.9.2) no valid post-route SDF for this design can be produced**, so nothing is
cited and `7.digital` stays `unmet` / `no_evidence` in
`signoff/block-manifest.signoff.json`. Verified 2026-11-15 (#174); three gaps,
each checked live:

1. **`klt place-and-route` refuses the SPEF/SDF request outright.** Adding
   `post_route_spef: true` and `post_route_sdf: true` to
   `layout/pnr-request.json` is rejected during request validation, before
   any engine runs:

   > request.post_route_spef requires a known klt extract deck for cell_library
   > 'gf180mcu_fd_sc_mcu7t5v0' (supported: asap7sc7p5t_rvt,
   > gf180mcu_fd_sc_mcu9t5v0, sg13g2_stdcell, sky130_fd_sc_hd)

   klt's cell-library → extraction-deck bridge table knows only the gf180mcu
   9-track 5 V family; the controller is mapped to the 7-track family. The
   gf180mcu parasitics deck itself is routing-stack RC data, so this is a
   missing one-line bridge entry, not a capability gap — filed generically as
   [klayout-tools#5825](https://github.com/2AMLogic/klayout-tools/issues/5825).
   The two request flags must stay out of `layout/pnr-request.json` until a pin
   carries the bridge entry: at 0.9.2 they make `layout/pnr.sh` fail.

2. **A standalone SPEF cannot substitute.** The exact invocation, re-run at
   the pin 2026-11-15 (identical result bare and with `--top-cell-pins`):

   ```
   klt extract layout/efuse_otp_ctrl.gds --deck gf180mcu --parasitics \
       --top efuse_otp_ctrl --spef out.spef -o out.cir
   ```

   It exits 0 and writes a well-formed SPEF, but the gf180mcu extraction deck
   does not recognize the placed standard cells — the run flattens them to
   3106 transistor devices with no cell instance — so design net names do not
   survive intact (full-file classification of all 855 `*D_NET` records,
   2026-11-15): **532 escaped-anonymous `\$N`** (a numbering klt itself
   documents as unstable across klayout versions or hosts —
   klayout-tools#1063), **285 `|`-joined merged-label compounds** (99
   distinct names, exactly the run's compound `*PORTS` entries), and **38
   bare labels** (`VDD`, `VSS`, `Z`, `ZN`, …). The compounds show the
   mechanism rather than contradict it: cell-internal pin labels and
   top-level routing labels land on one electrical net and KLayout joins
   them — the deck's own report, from this run: "net 'I1|Z|row_sel[7]'
   merges 3 distinct labels (I1, Z, row_sel[7]) onto one net"; a label
   drawn on unconnected shapes splits across hundreds of nets instead
   ("label 'ZN' is drawn on 154 separate nets"), and 6 layers carrying 375
   shapes sit outside the deck's connectivity graph entirely. Splitting each
   compound on `|` and bus-base-normalizing, **12 design identifiers** appear
   as merge components (`busy clk dout prog_en prog_strobe rd_en rst
   sense_en sense_in addr col_sel row_sel`) — but only inside merged labels,
   never as net names: **0 of the design's 228 nets**
   (`layout/efuse_otp_ctrl.asbuilt.v`) match any `*D_NET` name, exact-name
   or bus-normalized. `read_spef` would
   annotate no nets, so an SDF from that session would look like a
   post-route measurement while carrying no routed parasitics — filed
   generically as
   [klayout-tools#5826](https://github.com/2AMLogic/klayout-tools/issues/5826).

3. **`klt sta` cannot fall back to an estimate-parasitics SDF.** Its
   `request.sdf` flag hard-requires `request.spef` ("an SDF written without
   the routed parasitics would not be a post-route delay file"), and no
   correlating SPEF is producible per gap 2.

When a pin carries both fixes, the path is the one the curation planned: add
the two flags to `layout/pnr-request.json` (one re-route then emits the stream
and an SDF whose instance paths match its own `asbuilt.v`), teach
`layout/pnr.sh` to copy `spef_sta.sdf_path` out beside the stream, and drive
`verification/runner.py`'s gate-level request with `options.sdf`. Two
decisions already made for that run, so they need not be re-derived: annotate
the SDF's `typ` corner (the P&R flow's timing deck, `tt_025C_1v80`, is
expected to write identical min/typ/max triples from one session), and use
`options.sdf.entries: "interconnect"` — klt's validated net-delay
back-annotation mode (klayout-tools#2364 found IOPATH annotation kills a
design at any clock period — a sky130/Icarus-13 finding, and `interconnect`
is the conservative choice either way). The annotated run must also obey the bench's own
timing: `test_efuse_otp_ctrl.py` clocks the DUT at 10 ns, and
`sim/controller-sta/sta-10ns.report.json` measures +4.48 ns setup slack at
`tt_025C_3v30` (the 100 MHz case fails only at `ss_125C_3v00`), so the run is
expected to be verdict-identical to the unannotated one — passing alone is
weak evidence; quote `environment.sdf.partial` and `.dropped` when it exists.

## Testbench inventory

The item-9 inventory is `signoff/attest/item9.json`. Cold start for all of it, from a
fresh clone with the pinned tools installed (above, plus Icarus Verilog 13.0, `uv`
on PATH, and network for the first fetch of the pinned klt and cocotb):

```bash
sim/cold-start.sh
```

It runs the controller bench, then `--dry-run` of each analog request set. `--dry-run`
validates the request set only; it runs no corner and says nothing about margin or
current. The campaigns are the batch commands in the table.

| Spec row | Bench | Cold-start (validate) | Campaign (batch, writes a record) |
|---|---|---|---|
| Program current (A2, decision 0002) | `sim/program-select/run.sh`, `cell.cir.in`, `summarize.py` | `sim/program-select/run.sh --dry-run` | `sim/program-select/run.sh` |
| Sense margin (A4/A5/A6, decision 0003) | `sim/sense-margin/run.sh`, `sense.cir.in`, `summarize.py` | `sim/sense-margin/run.sh --dry-run` | `sim/sense-margin/run.sh` |
| Controller behaviour (decision 0004) | `verification/run.sh`, `runner.py`, `test_efuse_otp_ctrl.py` | `verification/run.sh` (runs the bench itself) | `verification/run.sh --negative-control` |

This table does not restate the versions: the tool pins are the `pins` block of
`signoff/attest/item9.json` (checked in CI) and `sim/pdk.json` (PDK revision and variant),
and each `record.json` names the klt and ngspice that actually produced it — the analog
benches call the `klt` on `PATH` rather than gating on the pinned release.

The batch campaigns need access to the batch fleet; the cold start does not run a corner.
