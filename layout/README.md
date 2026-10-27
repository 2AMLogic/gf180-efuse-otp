# layout

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

`sha256(efuse_otp_array.gds)` = `a4a198d06061ea6cee2d2c41eff233cf695deeb29b37f6a9bc2b0f7c5a558a5b`
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
  `rsh_ppolyf_u` = 350 Ω/sq. The 1 µm width is an assumption, not a sourced
  value.

## What is not claimed

- **No routing and no connectivity.** Devices and cells are placed; no wire
  joins them, so the stream is not a circuit and does not match the netlist
  until routing is added.
- **No DRC, no LVS, no ERC.** Those are #31, #32 and #33. `klt drc` does not
  run the `EF.*` rules at all (`spec/efuse-otp.md` §1.3), so a DRC result on
  this stream would not cover them.
- Cell-to-cell clearance is a fixed 2 µm between bounding boxes, not a
  rule-derived spacing.
- The `item2-analog.attest.json` envelope is hand-written: `klt signoff
  --attest` has no producer for item 2 (klayout-tools#4188, #4221).
