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
it cannot go stale against the check it describes. `summarize.py` runs under
`python3 -I`, so it imports the module through an explicit `sys.path` insert.

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

Result (record `20261108T235928Z-f6eeac7`, after the column driver `Mdrv` went from
W = 100 um to 3 x 100 um, option (a) of the 2026-11-08 operator ruling): all 135 points pass at
each fuse value; binding corner ss / 125 C / vdd33 2.97 V / vprog 4.5 V / 260 ohm at
10.97 mA (>= 10 mA, A2); negative control reads fail. The earlier record
`20261030T230649Z-f6eeac7` (8.835 mA at the same corner, 100 um driver) and the failed first
attempt `20261108T235750Z-f6eeac7` (single 300 um device, outside the `pfet_06v0` model bin
of W <= 100 um, so all 45 corners errored in ngspice) are kept as append-only evidence. The
fuse range and the 20 ohm route are assumptions (A4, no documented source).

## Sense-margin bench

`sim/sense-margin/run.sh` runs the committed sense path (`efuse_sense`, `efuse_comp`)
against intact 140/200/260 ohm (A4) and programmed 630/900 ohm/open (A5) fuse values and
the 400 ohm reference (A6) over the decision-0005 grid, plus a negative control with the
reference moved inside the intact range. It submits 8 requests with `klt sim --batch-set`
(batch only) and writes `sim/sense-margin/records/<stamp>-<rev>/record.json`. Assumptions
and the record layout: `sim/sense-margin/README.md`.

## Testbench inventory

The item-9 inventory is `signoff/attest/item9.json`. Cold start for all of it, from a
fresh clone with the pinned tools installed (above, plus Icarus Verilog 13.0, Yosys 0.67
and network for the first `pip install` of the pinned cocotb):

```bash
sim/cold-start.sh
```

It runs the controller bench, then `--dry-run` of each analog request set. `--dry-run`
validates the request set only; it runs no corner and says nothing about margin or
current. The campaigns are the batch commands in the table.

| Spec row | Bench | Cold-start (validate) | Campaign (batch, writes a record) | Pinned |
|---|---|---|---|---|
| Program current (A2, decision 0002) | `sim/program-select/run.sh`, `cell.cir.in`, `summarize.py` | `sim/program-select/run.sh --dry-run` | `sim/program-select/run.sh` | open_pdks `f6eeac7`, ngspice 42, klt 0.8.0 |
| Sense margin (A4/A5/A6, decision 0003) | `sim/sense-margin/run.sh`, `sense.cir.in`, `summarize.py` | `sim/sense-margin/run.sh --dry-run` | `sim/sense-margin/run.sh` | open_pdks `f6eeac7`, ngspice 42, klt 0.8.0 |
| Controller behaviour (decision 0004) | `verification/run.sh`, `runner.py`, `test_efuse_otp_ctrl.py` | `verification/run.sh` (runs the bench itself) | `verification/run.sh --negative-control` | Icarus 13.0, Yosys 0.67, cocotb 2.1.0 |

The batch campaigns need access to the batch fleet; the cold start does not run a corner.
