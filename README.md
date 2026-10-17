# gf180-efuse-otp

An eFuse one-time-programmable (OTP) array on the
[gf180mcu](https://github.com/google/gf180mcu-pdk) open PDK, built on the
PDK's documented eFuse layers — fuse cells, row/column addressing, a program
path and a sense path — designed and verified by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools), xschem + ngspice
for the analog paths and Yosys/OpenROAD for the controller.

**Private repo.** Visibility is an operator decision; nothing here is
published.

**Status: just opened, specification phase.** Nothing is designed yet.

## What the block is

- **Cell**: the gf180mcu eFuse — a poly fuse drawn on Poly2 with the
  `PLFUSE` layer inside an `EFUSE_MK` marker, with anode and cathode
  defined by `LVS_Source`. The PDK's `EF.*` rule set fixes most of the fuse
  geometry (fuse width and length, anode and cathode size, contact count),
  so the cell is largely constrained by the rules; what this repo designs is
  everything around it.
- **Array**: rows and columns of fuse cells, each behind a program-select
  device that must carry the program current.
- **Program path**: the select device, its drive and its supply, sized to
  deliver the programming current at the worst corner.
- **Sense path**: a read circuit that distinguishes intact from programmed
  fuses with margin at every corner.
- **Controller**: addressing, program sequencing and read, behind a simple
  synchronous interface.

The PDK already ships an eFuse primitive (`gf180mcu_fd_pr`) and a set of
precompiled eFuse macros (`gf180mcu_re_efuse`) produced by an open eFuse
compiler. Those are the reference and the comparison. This repo is not
wrapping them; where the honest answer is "the shipped macro already does
this correctly," record that — it is a real result.

## Why this block

Three surfaces this block exists to exercise:

- **A rule-defined device.** The eFuse rules are exact-value rules
  (min = max), and klt's handling of them on a full array is untested.
- **A destructive analog event.** Programming is a one-shot, current-driven
  change of the fuse; standard compact models do not simulate it. What the
  pre-silicon evidence can and cannot show is a spec question, not a detail.
- **Two resistance populations.** Sense margin depends on the intact and
  programmed resistance distributions, and where those numbers come from has
  to be documented, not assumed.

## Target specification (DRAFT — engineering to ratify, see issue #1)

All figures are targets.

| Parameter | Target | Fallback | Stretch |
|---|---|---|---|
| Array | 256 bits (32 × 8) | 8 bits (1 × 8) | 1 kbit |
| Interface | synchronous, native address / program-enable / read | asynchronous parallel read | serial interface |
| Program supply | external for this test vehicle | — | on-die (decision record) |
| Program path | worst-corner current delivery at or above the required program current | — | — |
| Sense margin | positive at every corner, over the documented intact/programmed resistance ranges | — | — |
| Signoff | DRC (including every `EF.*` rule) + LVS clean | — | — |

Maturity ladder: spec ratified → cell and program path simulated across PVT
→ sense path simulated across PVT → array DRC/LVS-clean → controller
verified → assembled and LVS-clean → shuttle seat → measured silicon.
**Current position: pre-spec.**

## Repo layout

```
spec/          ratified spec + decision records
design/        program and sense path schematics (xschem)
rtl/           controller sources
verification/  cocotb testbenches
sim/           testbenches + PVT corner results (ngspice)
layout/        GDS + DRC/LVS reports (klayout-tools driven)
measurements/  silicon characterization (empty until tape-out)
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
