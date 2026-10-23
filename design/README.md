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
