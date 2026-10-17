# gf180-efuse-otp — agent instructions

Private canary block: an eFuse one-time-programmable array on GlobalFoundries
gf180mcu, built on the PDK's documented eFuse layers, with row/column
addressing, a program path, a sense path and a synchronous controller.
**Mixed-signal**, so both flows apply.

- **PDK**: gf180mcu (open PDK). Analog: xschem + ngspice. Digital: cocotb +
  Icarus, Yosys, OpenROAD. Layout, DRC and LVS through klayout-tools (`klt`).
  The eFuse is a Poly2 fuse under the `PLFUSE` and `EFUSE_MK` layers, and the
  PDK's `EF.*` rules fix most of its geometry; the program-select devices
  are where the dual gate oxide (3.3 V and 5/6 V devices) matters.
- **PRIVATE, and that is a standing operator decision.** Do not propose,
  prepare, or perform a visibility flip; do not mirror content anywhere
  public (issues and PRs in this repo are private surfaces; anything outside
  this repo is not). Visibility changes are operator-only, as everywhere in
  the fleet — treat that rule as load-bearing here, not boilerplate.
- **Scope firewall (hard rule).** This repo discusses eFuse device physics,
  array/addressing design, programming and sensing circuits, the controller,
  and simulated or measured yield/margin — nothing else. Do not write about
  applications or use cases for a one-time-programmable memory, do not
  speculate about why 2AM wants one, and do not reference any other 2AM repo
  except the public gf180 canaries (for circuit/flow conventions) and
  `2AMLogic/klayout-tools` (for tool issues). If a task appears to need
  application context to proceed, stop and leave it for the operator — that
  need is itself the signal the task doesn't belong here. Fleet-ops plumbing
  is exempt: fleet tooling may reference the fleet's own infrastructure,
  while design content remains subject to this firewall and the
  private-visibility rule is unchanged.
- **Programming is an analog event, not a digital write.** No compact model
  simulates the fuse changing state. Pre-silicon claims are limited to what
  can be simulated: the program path delivering the required current at the
  worst corner, and the sense path's margin over stated intact and
  programmed resistance ranges. Every such range cites its source; a range
  with no documented source is flagged as an assumption, never a fact.
- **The rule-defined cell is the risk.** The `EF.*` rules are exact-value
  rules. Establish first whether klt's gf180mcu deck runs them; if it does
  not, that is a friction item to file, not a rule to skip.
- **Scope discipline.** No `consumes:` edge is declared. The PDK's eFuse
  primitive and its precompiled `gf180mcu_re_efuse` macros (and the open
  compiler that produced them) are reference and comparison: cite them, do
  not reimplement them.
- **Friction protocol (the canary's job)**: every time klayout-tools is
  awkward, missing a capability, or wrong for what you need, file an issue
  at `2AMLogic/klayout-tools` describing the tool gap generically — that
  tracker is public, so keep ALL design detail and this repo's name out of
  the issue body; describe the gap, not the design.
- **Verification is the product**: no claim without a testbench. PVT corners
  on every recorded result; `sim/` results are append-only evidence.
- Spec changes go through `spec/` with a decision record; agents do not
  relax the ratified spec to make results pass.
