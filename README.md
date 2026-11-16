# gf180-efuse-otp

An eFuse one-time-programmable (OTP) array on the
[gf180mcu](https://github.com/google/gf180mcu-pdk) open PDK, built on the
PDK's documented eFuse layers — fuse cells, row/column addressing, a program
path and a sense path — designed and verified by AI agents driving
[klayout-tools](https://github.com/2AMLogic/klayout-tools), xschem + ngspice
for the analog paths and Yosys/OpenROAD for the controller.

**Private repo.** Visibility is an operator decision; nothing here is
published.

**Status: sense path simulated across PVT** (on assumed ranges — the current
position under [Target specification](#target-specification) carries the
caveats). Committed on `main`:

- the PDK smoke record and the program-select width sweep record;
- the controller RTL with its cocotb bench and negative control, and a mapped
  gate-level netlist;
- the analog schematics and netlist in [`design/`](design/), including the sense
  path ([`efuse_sense.sch`](design/efuse_sense.sch),
  [`efuse_comp.sch`](design/efuse_comp.sch)) and its margin campaign in
  [`sim/sense-margin/`](sim/sense-margin/) (#28);
- a placed analog layout stream and the routed controller layout
  ([`layout/efuse_otp_ctrl.gds`](layout/efuse_otp_ctrl.gds),
  [`layout/pnr-report.json`](layout/pnr-report.json));
- DRC reports for both partitions
  ([`layout/drc-array.report.json`](layout/drc-array.report.json),
  [`layout/drc-ctrl.report.json`](layout/drc-ctrl.report.json)); the `EF.*`
  rules are not yet evaluated by the deck (#60);
- the signoff record.

Not started: analog routing, LVS (#32) and ERC (#33). Verdicts of record are in
[`signoff/block-manifest.signoff.json`](signoff/block-manifest.signoff.json).

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

## Target specification

The ratified spec is [`spec/efuse-otp.md`](spec/efuse-otp.md): the PDK
documentation survey, the parameter table (target / fallback / stretch), the
PVT corner set, and the limits of pre-silicon evidence. Decision records are in
[`spec/decisions/`](spec/decisions/).

Maturity ladder: spec ratified → cell and program path simulated across PVT
→ sense path simulated across PVT → array DRC/LVS-clean → controller
verified → assembled and LVS-clean → shuttle seat → measured silicon.
**Current position: sense path simulated across PVT** — reading the ladder
sequentially, the last rung reached with no gap beneath it. Verdict of record:
[`signoff/block-manifest.signoff.json`](signoff/block-manifest.signoff.json);
the rung's evidence is the 45-corner sense-margin sweeps and the Monte Carlo
record under `sim/sense-margin/` and `sim/sense-mc/`. That claim rests on the
**assumed** intact/programmed ranges A4/A5 and an unsourced
reference-tolerance sigma — rows P10/C2 grade `partial` in
[`measurements/characterization/README.md`](measurements/characterization/README.md)
— not on a real fuse's margins. The next rung (array DRC/LVS-clean) is **not**
reached: DRC is clean but uncited (#60 — the curated deck does not evaluate
the foundry `EF.*` set) and LVS is `unmet` (#32), so the block is not an
LVS-clean array.

## Reproduce

Every committed result and the command that regenerates it. Run from the repo
root. `sim/` records are append-only evidence: re-running creates a new record
and never replaces a committed one.

| Result | Command | Needs | Produces |
|---|---|---|---|
| PDK smoke | `sim/pdk-smoke/run.sh` | ngspice, jq, ciel 2.6.1 with the PDK pinned in `sim/pdk.json`; cold start in [`sim/README.md`](sim/README.md) | new `sim/pdk-smoke/records/<stamp>-<rev>/` |
| Program-select width sweep | `sim/program-select/run.sh` | the same PDK tree, plus the klt batch fleet (15 `klt sim` requests; a failed submit is reported, not re-run locally) | new `sim/program-select/records/<stamp>-<rev>/record.json`; result in [`design/README.md`](design/README.md) |
| Controller bench | `verification/run.sh` | python3, uv, network for the pinned klt and cocotb, Icarus Verilog 13.0 | `ALL CHECKS PASSED` |
| Controller negative control | `verification/run.sh --negative-control` | same | `NEGATIVE CONTROL OK` (exit 0 only if every seeded defect is caught) |
| Latch check | `rtl/synth.sh` | Yosys 0.67 | exit 0 and no output; Yosys asserts no latch cell survives synthesis and names any it finds. Log in `flow/build/synth.log` |
| Signoff record | `uvx --from "$(cat signoff/klt-pin.txt)" klt signoff --manifest signoff/block-manifest.json --tiers-doc signoff/design-evidence-tiers.md --format json > signoff/block-manifest.signoff.json` | uv; exit 3 (items unmet) is expected | byte-identical to the committed `signoff/block-manifest.signoff.json` |

`verification/run.sh` refuses any Icarus version other than the pinned one;
`ALLOW_TOOL_MISMATCH=1` overrides this and is not used in CI. `rtl/synth.sh`
checks no version itself; in CI the Yosys version is fixed by
`scripts/ci/install_eda.sh`. Details: [`verification/README.md`](verification/README.md),
[`rtl/README.md`](rtl/README.md), [`signoff/README.md`](signoff/README.md)
(regenerating the gate-level netlist and the item attestations).

CI (`.github/workflows/ci.yml`) re-runs the controller bench, its negative
control and the latch check; the `harness` job's signoff and attestation checks
are listed in [`signoff/README.md`](signoff/README.md), "What CI does and does
not check". It does not run the ngspice flow (it needs the PDK).

`npm run -s check:ci` is the local pre-flight: the subset of those checks that
needs nothing but python3, bash and jq — the checker self-tests, the
evidence-format check, the item 6 spec-binding check, the `pdk_env.sh`
self-test (`sim/lib/test_pdk_env.sh`), the klt helper self-test
(`signoff/test-klt.sh`, which fakes `uvx` on `PATH` and asserts on the argv the
pinned-klt facets emit, so it never invokes a real `klt`), the program-select
summarize self-test (`sim/program-select/test_summarize.py`, which pins that
the record describes the submitted grid rather than whatever reports are
present) and the sense-margin summarize self-test
(`sim/sense-margin/test_summarize.py`, which pins that the record describes
the submitted request set rather than whatever reports are present). The
workflow runs none of those last four. It
deliberately leaves out every check that needs an EDA tool, the PDK or a diff
base, so a green `check:ci` is not a prediction that CI will pass.

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
