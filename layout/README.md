# layout

Routed layout of the digital partition (`efuse_otp_ctrl`), produced by
`klt place-and-route` from the mapped netlist `rtl/efuse_otp_ctrl.gl.v`. The
analog partition's layout does not live here yet.

| File | Role |
|---|---|
| `pnr-request.json` | The `klt place-and-route` request: `gf180mcu_fd_sc_mcu7t5v0`, 40 % utilization, 10 µm core margin, the `gf180mcu_7t_6M` PDN preset (the klt-tabulated recipe transcribed from OpenROAD-flow-scripts), I/O pins on Metal3 (horizontal) / Metal2 (vertical), `target_stage: route`, seed 1, `portable_paths`. |
| `pnr.sh` | Runs the flow with the pinned klt (`signoff/klt-pin.txt`), asserts `status: ok` and `power.pdn: true`, and writes the files below. `--check` runs `klt place-and-route --check` plus the GDS sha256; `--check --rerun` re-runs the flow and diffs the verdict-bearing fields. |
| `pnr-report.json` | Committed `--format json` response. Route stage reached, 0 route DRC and 0 antenna violations, `power.pdn: true`, `power.tapcell_master: gf180mcu_fd_sc_mcu7t5v0__filltie`. |
| `efuse_otp_ctrl.gds` | Routed GDS (standard-cell GDS views merged in by klt). Its sha256 is in `efuse_otp_ctrl.gds.sha256`. |
| `efuse_otp_ctrl.asbuilt.v` | `verilog_path` output: the as-built gate-level netlist (CTS buffers, resizes, antenna diodes included). This, not `rtl/efuse_otp_ctrl.gl.v`, is the reference for the controller LVS run. |
| `attest.sh`, `pnr.attest.json` | The T1 item 2 (digital) attestation: a generic envelope bound to the GDS, with a `layout/pnr.sh` regeneration claim (geometry digest). klt has no `--attest 2`, so `attest.sh` assembles it from the committed report (klayout-tools issues #4188, #4221). |

## Reproduce

```sh
layout/pnr.sh --check            # cheap: input netlist and deck hashes, GDS sha256
layout/pnr.sh --check --rerun    # full: re-runs OpenROAD (about 2 minutes)
layout/pnr.sh && layout/attest.sh   # regenerate, then re-attest
```

Needs `openroad` on `PATH` and the gf180mcuD PDK (`PDK_ROOT`, default `~/.ciel`).
`layout/.klt/` is scratch and is gitignored.

## Assumptions

- **Clock period 100 ns** (`constraints.clock_period_ns`) is a P&R target chosen
  to drive CTS and timing-driven steps, not a requirement from the spec: the spec
  states no clock frequency. The `worst_slack_ns` in the report is against this
  assumed period, so it is not evidence of a timing margin (STA is a separate
  item).
- Utilization, core margin, I/O layers and seed are floorplan choices, not spec
  values.
- Only the typical-corner liberty is used for the P&R timing figures; the
  report's `corners` are not a PVT sign-off.
