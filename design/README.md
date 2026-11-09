# design

## 2026-10-23: program-select width (`nfet_06v0`)

**Result: 60 µm (L = 0.7 µm, nf = 1) is the smallest swept width at which every
point passes the 10 mA requirement.** Of the widths swept (20, 40, 60, 80,
100 µm), 20 µm fails 112 of 135 points and 40 µm fails 1 (9.66 mA at ss, 125 °C,
4.5 V, 260 Ω); 60, 80 and 100 µm pass all 135. The sweep is coarse, so 60 µm is
a swept value, not a minimum.

Evidence: `sim/program-select/records/20261023T174839Z-f6eeac7/record.json`
(PDK `open_pdks f6eeac7`, ngspice 46 on the batch fleet, 15 jobs listed under
`remote_job_ids`).

**Grid.** Process `typical`/`ff`/`ss`/`fs`/`sf` × −40/25/125 °C × program supply
4.5/5.0/5.5 V (decision 0005) × fuse 140/200/260 Ω (A4) = 135 points per width.

**Binding corner at 60 µm.** ss, 125 °C, 4.5 V, fuse 260 Ω: 11.99 mA (Vgs 4.5 V,
Vds 1.14 V). At the documented 200 Ω fuse the minimum over all corners is
13.66 mA. The same corner binds at every width, as expected: lowest supply,
slowest process, hottest, highest fuse resistance.

**Voltage stress, as simulated.** Across the 135 points at 60 µm, Vgs reaches
5.5 V (gate = supply at the 5.5 V corner) and Vds reaches 2.32 V. Both are
within 6.0 V. That 6.0 V is an **assumed limit**: the model library names
`nfet_06v0` the "6.0V NMOS" but I found no numeric rating in it or in `spec/`,
so this is not a rating check. A later search (2026-10-23) of the open PDK
documentation (gf180mcu-pdk.readthedocs.io: `analog/spice/elec_specs/elec_specs_2`
"2.0 Medium Voltage Devices (6V)", `elec_specs_7_5` "7.3A 6V NMOS SAB",
`IPs/IO/gf180mcu_fd_io/conditions`) also found no Vgs/Vds/Vgd limit. What it
does document for the 6V NMOS (NE2, W/L 10/0.7) is characterisation bias, not a
rating: Idsat at |Vds| = |Vgs| = 6 V, Ioff at |Vds| = 6.6 V, and BVDSS 8.5 V min
(11 V typ). The foundry design-rule and reliability documents were not
available, so the limit stays an assumption; the 5.5 V Vgs and 2.32 V Vds seen
here are below the 6 V test bias, which is context only. The 3.3 V fallback is not taken.

**Assumptions (no documented source; also in `record.json`).**

- Routing resistance: 20 Ω, one lumped resistor in series with the fuse.
- Gate drive: ideal source equal to the program supply at the corner
  (Vgs = Vprog); the level shifter is not modelled.
- Fuse at 140 and 260 Ω is a plain resistor. The PDK `efuse` subcircuit is
  `200*(1-pblow)+900*pblow` and cannot reach those values, so 200 Ω uses the
  subcircuit with `pblow=0`.
- 10 mA (A2) and 140–260 Ω (A4) are the ratified spec assumptions, unchanged.

**What this does not show.** Only that the program path delivers the assumed
current into a resistor standing in for the intact fuse (spec section 3). It
says nothing about the fuse changing state.

**Variant.** The pinned tree is `gf180mcuC`; the batch fleet image carries
`gf180mcuD`. `run.sh` simulates from `gf180mcuD` and refuses to run unless
`sm141064.ngspice`, `sm141064.spice` and `design.ngspice` are byte-identical
between the two at the pinned revision.

## 2026-10-27: schematics and netlist (T1 item 1, analog)

Structure only. **No simulation result is claimed here**; every device size in
the new cells is a placeholder, to be set by the program-path (#28) and sense
(#34, #36) simulations. The `nfet_06v0` select at W = 60 µm, L = 0.7 µm is the
width from the result above.

| Cell | Contents |
|---|---|
| `efuse_bitcell` | PDK `efuse` subcircuit (`efuse_prim.sym`, model `efuse`, `pblow=0`) in series with the select `nfet_06v0` |
| `efuse_row` | 8 bitcells sharing `wl` |
| `efuse_ls` | non-inverting 3.3 V → `vprog` level shifter: 3.3 V inverter, `nfet_06v0` pull-downs, cross-coupled `pfet_06v0` |
| `efuse_rowdrv` | `wl` = level-shifted `row_sel` |
| `efuse_coldrv` | `pfet_06v0` from `vprog` to `bl`, gate = level-shifted NAND(`col_sel`, `prog_strobe`); read switch `nfet_06v0` `bl`–`sbl`, gate = `col_sel` AND `sense_en` |
| `efuse_comp` | clocked comparator, PMOS input pair, NMOS cross-coupled latch (`clkn` high = reset) |
| `efuse_sense` | equal bias currents (`pfet_03v3`) into `sbl` and a 400 Ω reference (A6, decision 0003) behind a dummy switch and select; NAND(`clk`, `sense_en`) clocks the comparator; NOR SR latch holds `sense_out` (1 = programmed) |
| `efuse_otp_array` | top: 32 × 8 (decision 0001), bit address = row × 8 + column |

**Topology choices not fixed by the spec** (the spec is not changed):

- Level shifter: the standard cross-coupled-PMOS form, because the select gate
  must see `vprog` (5 V) while the controller is 3.3 V.
- Unselected bit lines are not pulled down: in the selected row an unselected
  column's `bl` is held at 0 by its own fuse and select, and in other rows the
  select is off. Whether leakage on floating `bl` matters is for simulation.
- Comparator: PMOS input pair because the sense inputs sit near `vss` (small
  read current across 140–900 Ω). Sense compares the voltage developed by
  equal bias currents in the fuse path and the 400 Ω path, so the comparison is
  against the reference resistor as decision 0003 states, realised ratiometrically.
- The program current now also flows through the column `pfet_06v0` (W = 100 µm
  placeholder); the 60 µm select result above did not include it, so the
  program-path claim needs re-simulation with this driver (#28).
- 2026-11-08 (#34): `Mdrv` is now `m=3` x W = 100 µm (300 µm total; one 300 µm device is
  outside the `pfet_06v0` model bins). At 100 µm the corner campaign gave 8.835 mA at the
  binding corner (below A2's 10 mA); at 300 µm it gives 10.97 mA. The layout report
  (`layout/efuse_otp_array.report.json`) still reflects the 100 µm driver.

**Comparator clock.** `clk` is the digital partition's system clock. It enters
the analog partition as a boundary input and is gated there with `sense_en`
(`NAND(clk, sense_en)` → `clkn`), so the comparator evaluates only during the
settle window. The partition boundary is stated in `signoff/block-manifest.json`.

**Regenerate the netlist** (pinned klt, runs from `design/` so the cell symbols
resolve; needs xschem and the pinned PDK tree):

```sh
design/regen-netlist.sh           # write design/efuse_otp_array.spice
design/regen-netlist.sh --check   # exit 3 = drifted
```

The netlist embeds the generating checkout's absolute `sch_path`; `klt netlist
--check` normalises it, so the check holds from any checkout.
