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
`program-select.sch` is the schematic (netlist it with `klt netlist`); the
swept deck is `cell.cir.in`. Result and derivation: `design/README.md`.

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
reference moved inside the intact range. It submits 8 requests with `klt sim --batch-set`
(batch only) and writes `sim/sense-margin/records/<stamp>-<rev>/record.json`. Assumptions
and the record layout: `sim/sense-margin/README.md`.

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
