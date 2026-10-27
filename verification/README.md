# verification

cocotb + Icarus bench for `rtl/efuse_otp_ctrl.v`.

```sh
verification/run.sh                    # all parameter sets, exit 0 iff every check passes
verification/run.sh --negative-control # exit 0 only if every deliberately broken variant is caught
```

`run.sh` checks the tool versions (Icarus Verilog 13.0, Yosys 0.67;
`ALLOW_TOOL_MISMATCH=1` overrides), creates `verification/.venv` with the pinned
`cocotb==2.1.0` from `requirements.txt` (first run needs network; nothing is
installed into the host), then runs `runner.py`.

## Parameter sets

32 x 8 and 1 x 8 arrays, each at minimum (1 us), nominal (10 us) and maximum
(100 us) pulse width at 10 MHz (10, 100, 1000 cycles), plus the 0 us and 500 us
clamp cases, odd settle counts, and 100 us at 100 MHz (10000 cycles, which
needs the 64-bit width computation).

## Checks (`test_efuse_otp_ctrl.py`, 12 per parameter set)

- no program output at power-up with X inputs, or during reset, before any clock edge;
- no program before arming: request at the first and second edge after release
  is ignored, the third is accepted; enable stuck high never programs;
- reset mid-pulse drops every program output immediately and re-disarms;
- program pulse exactly `PULSE_N` cycles, selects match the latched address,
  `busy` spans select set-up plus pulse, for first/last/middle addresses;
- address change while busy ignored; request while busy dropped; back-to-back
  requests give two full pulses;
- read: `sense_en` exactly `SETTLE_CYCLES`, `dout` taken at the closing edge;
  read works before arming; read wins over a simultaneous program request.

## Negative control

`--negative-control` copies the RTL into `build/`, applies one-line defects
(arming bypassed, pulse off by one, program strobe not reset-gated) and runs the
nominal 32 x 8 bench on each. It exits 0 only if the named check fails for every
defect, and non-zero (including when a pattern no longer matches the RTL) otherwise.

Expected: `ALL CHECKS PASSED` for `run.sh`, `NEGATIVE CONTROL OK` for the mode above.
CI runs both modes in the `controller` job of `.github/workflows/ci.yml`.

## klt functional-verification

`verification/klt-fv.sh [outdir]` runs the same bench through the pinned
`klt functional-verification`, one request per parameter set. The requests are
generated from `CONFIGS` in `runner.py` (`runner.py --emit-klt-requests DIR`), the
single table of parameter sets; expected pulse/settle counts are passed through the
environment as in `runner.py`. Reports are kept in `sim/controller-fv/`
(9 sets, 12/12 checks each).
