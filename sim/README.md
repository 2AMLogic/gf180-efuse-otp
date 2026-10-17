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
