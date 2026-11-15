# verification

cocotb + Icarus bench for `rtl/efuse_otp_ctrl.v`.

```sh
verification/run.sh                    # all parameter sets, exit 0 iff every check passes
verification/run.sh --negative-control # exit 0 only if every deliberately broken variant is caught
```

`run.sh` checks the tool version (Icarus Verilog 13.0;
`ALLOW_TOOL_MISMATCH=1` overrides), then runs `runner.py`, which drives every
parameter set through `klt functional-verification` from the pinned klt
(`signoff/klt-pin.txt`). The pinned `cocotb==2.1.0` from `requirements.txt` is
supplied to klt's throwaway environment (first run needs network; nothing is
installed into the host). `runner.py` itself needs only the standard library.

There is one execution path: the reports CI gates on and the reports committed
under `sim/controller-fv/` are produced by the same code, so neither can drift
past the other. A run that cannot produce a klt report fails loudly rather than
reporting a pass.

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

`--negative-control` copies the RTL into `build/mutants/`, applies one-line
defects (arming bypassed, pulse off by one, program strobe not reset-gated) and
runs the nominal 32 x 8 bench on each, through the same klt path as every other
run. It reads each defect's verdict from the klt report's per-test
`tests[].status`, and exits 0 only if the named check fails for every defect,
and non-zero (including when a pattern no longer matches the RTL) otherwise.

Expected: `ALL CHECKS PASSED` for `run.sh`, `NEGATIVE CONTROL OK` for the mode above.
CI runs both modes in the `controller` job of `.github/workflows/ci.yml`.

## Reports

Every run writes one klt report per parameter set. By default they go to
`verification/build/` (gitignored) along with the generated requests
(`build/requests/`) and klt's run artifacts; `run.sh --reports DIR` puts the
reports in `DIR` instead.

`verification/klt-fv.sh [outdir]` is a thin wrapper over that option and is how
the committed reports in `sim/controller-fv/` were produced (9 sets, 12/12
checks each; default outdir `sim/controller-fv`). Those are append-only
evidence: regenerate to a temporary directory to compare, never over the
committed files.

`CONFIGS` in `runner.py` is the single table of parameter sets, and each
set's expected pulse/settle counts reach the bench through the environment.
