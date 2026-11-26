# sta

Standalone multi-corner static timing of the routed controller
(`klt sta`, pinned klt, `geometry_source: routed`, no SPEF: wire parasitics are
estimated from the routed DEF by OpenSTA).

```sh
python3 -I sta/check_route.py  # verify the retained DEF against the cited STA input
sta/run.sh /tmp/efuse-sta  # write fresh reports outside the committed records
```

The runner requires a complete routed result and finite constrained setup and
hold measurements at the five requested library corners in each report.
The 100 ns target passes with nonnegative setup and hold. A 10 ns timing miss
is reported as headroom. The 1 ns control must produce negative setup slack at
each corner. A missing report or unconstrained corner fails the run.

Requests: `sta-100ns.json` (10 MHz), `sta-10ns.json` (100 MHz case),
`sta-negative-control-1ns.json` (must go negative). All three use the same
five corners, the gf180mcu 7t5v0 library's 3.3 V family:
`ss_n40C_3v00`, `ss_125C_3v00`, `tt_025C_3v30`, `ff_n40C_3v60`, `ff_125C_3v60`.

## Mapping to decision 0005 (not a complete match)

Decision 0005 asks for `typical/ff/ss/fs/sf` x {-40, 25, 125 C} at 3.3 V +/-10 %.
The library offers no `fs`/`sf` corner, no 3.3 V-family `tt` at -40/125 C, no
`ss`/`ff` at 25 C, and brackets 3.3 V at 3.00/3.60 V (+/-9 %). Coverage here is
therefore the five corners above; the rest is a gap, not a pass.

## Result (routed DEF sha256 `3afa4360...b04a05`, seed 1 request, 2026-10-27)

| Corner | 100 ns setup / hold (ns) | 10 ns setup / hold (ns) |
|---|---|---|
| ss_n40C_3v00 | 92.31 / 1.61 | 2.31 / 1.61 |
| ss_125C_3v00 | 88.77 / 2.31 | **-1.23** / 2.31 |
| tt_025C_3v30 | 94.48 / 1.14 | 4.48 / 1.14 |
| ff_n40C_3v60 | 96.84 / 0.64 | 6.84 / 0.64 |
| ff_125C_3v60 | 95.36 / 0.91 | 5.36 / 0.91 |

## Current routed input

The retained controller DEF hashes to `ddba55a3ae45487bbb5e56959b29c436dc08217687b0eda79aff4673109d5adc`. The three STA requests read this file directly from a fresh checkout. A repository check compares its contents with the 100 ns report cited for digital item 5. [Controller DEF](../layout/efuse_otp_ctrl.def) · [Cited 100 ns report](../sim/controller-sta/sta-100ns.ddba55a3.report.json)

OpenROAD `26Q3-1510-g6cb3f2b704` reproduced the DEF and the as-built Verilog byte for byte with `layout/pnr.sh`, KLT 0.9.2 and the GF180D open_pdks revision `f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`. The executable came from `openroad/orfs@sha256:bb7f31697fb8466ab61852fc796376cc16d9df38f762ccb733218b8a5e55824b` on linux/amd64. The regenerated GDS used a different element ordering. KLayout 0.30.14 compared all 52 cells at zero database-unit tolerance, including their instances, text and properties. All 9,550 GDS elements matched within their respective cells.

The 100 ns replay matched all ten published setup and hold slacks. Minimum setup was 88.7679 ns at `ss_125C_3v00` and minimum hold was 0.64285 ns at `ff_n40C_3v60`. At 10 ns the hot slow setup miss was 1.23206 ns. At 1 ns every corner failed setup. All three runs used the retained route. [10 ns headroom](../sim/controller-sta/sta-10ns.ddba55a3.report.json) · [1 ns control](../sim/controller-sta/sta-negative-control-1ns.ddba55a3.report.json)

Decision 0006 (ratified 2026-11-08) sets the controller clock target at 10 MHz,
so the 100 MHz result below is out-of-spec headroom rather than a failure
against a requirement. Item 5 (digital) cites the 100 ns report only.

The 100 MHz case **fails setup at `ss_125C_3v00`** (44 violating endpoints, worst
path `_477_/Q` -> `_439_/D`, an internal register path). No clock, RTL or
constraint was changed to hide it. The 1 ns control goes negative at every
corner, so the check can fail. Every corner is `constrained`, but
`constraint_completeness` is `incomplete`: the 47 output endpoints carry no
output delay (none is specified in the spec), so I/O timing is not covered.
