# rtl

`efuse_otp_ctrl.v` is the synchronous controller (spec section 2 "Controller
interface" and "Controller behavior", decision 0004). Verilog-2001, one clock,
one synchronous reset, no latches, no gated clocks. It does not model the
analog program or sense paths.

## Interface

| Port | Dir | Meaning |
|---|---|---|
| `clk`, `rst` | in | Clock; active-high synchronous reset |
| `addr[AW-1:0]` | in | Bit address, `row*COLS + col`; an address `>= ROWS*COLS` is rejected |
| `prog_en` | in | A **rising edge** requests a program pulse |
| `rd_en` | in | A **rising edge** requests a read |
| `sense_in` | in | Clocked comparator output, 1 = programmed (assumed polarity for the sense partition) |
| `prog_strobe` | out | Program drive: exactly `PULSE_N` cycles per request |
| `row_sel`, `col_sel` | out | One-hot selects for the latched address |
| `sense_en` | out | High for exactly `SETTLE_CYCLES` cycles during a read |
| `dout` | out | `sense_in` as seen at the last settle edge; held until the next read |
| `busy` | out | High from the cycle after acceptance until the operation ends |

Parameters: `ROWS` (32), `COLS` (8), `AW` (`clog2(ROWS*COLS)`, 8; set it
explicitly, 3 for 1 x 8), `CLK_HZ`, `PULSE_US`, `SETTLE_CYCLES`. The pulse is
`round(PULSE_US * CLK_HZ / 1e6)` cycles with `PULSE_US` clamped to 1-100 us (A3:
no PDK source, spec section 1.2). Minimum, nominal (10 us) and maximum are three
elaborations, not a runtime port (decision 0004 defines no such port).

## Behavior

- **Arming.** Decision 0004 has no arm port, so arming is a registered state
  entered from reset: `released` is set on the first clock edge with `rst` low
  and `armed` on the second. A program request is accepted only when `armed` is
  already set, so the first acceptable request is the one presented at the third
  edge after release. Reads do not need arming. Nothing here changes the
  ratified interface.
- **Reset.** `prog_strobe`, `row_sel`, `col_sel`, `sense_en` and `busy` are
  registers ANDed with `~rst`, so they are inactive as soon as `rst` is asserted
  and from power-up, before any clock edge.
- **Request edge.** `prog_en`/`rd_en` act on a rising edge, and the edge detector
  resets to "was high". An enable stuck high through reset or power-up therefore
  never programs; it must be seen low first. A held-high `prog_en` gives one pulse.
- **Program.** Accepting edge latches the address and raises the selects; the
  strobe starts one cycle later (select set-up), stays high `PULSE_N` cycles and
  drops with the selects. `busy` spans set-up plus pulse.
- **Read.** Accepting edge latches the address and raises `sense_en` for
  `SETTLE_CYCLES` cycles; `dout` captures `sense_in` at the closing edge.
- **Address changes** while busy are ignored (the accepting-edge address is latched).
- **Requests while busy** are dropped, not queued.
- **`prog_en` and `rd_en` rising together:** the read runs, the program is dropped
  (a read is harmless; a program is irreversible).

## Synthesis check

```sh
rtl/synth.sh                     # gate: synth + check -assert + no-latch assertion; log in flow/build/synth.log
rtl/synth.sh --negative-control  # control: proves the gate can fail; log in flow/build/synth-negctl.log
```

Last result (Yosys 0.67): completes and exits 0, printing nothing. The gate is
an assertion, not a count: `rtl/synth.ys` ends by `script`-including
`rtl/latch-assert.ys`, so the run fails if any latch cell survives generic
synthesis, and Yosys names the offending cells on the way out. (`check -assert`
alone does not assert on latches.)

`rtl/latch-assert.ys` is the single source of the asserted pattern set: the
real gate and the negative control (`rtl/synth-negctl.ys`) both `script`-include
it, so a typo in the patterns blinds both gates together. The control
synthesizes the committed fixture `rtl/latch-negative-control.v` — one
deliberately observable level-sensitive assignment; it is a negative control,
never design RTL — through that same text, and `rtl/synth.sh
--negative-control` exits 0 only if the assertion fires, naming the fixture's
inferred latch cell. A gate that has gone blind (a typo'd pattern, a Yosys
renaming the latch cells) leaves the fixture synthesizing clean and fails the
control, the same way "Controller negative control" keeps the bench from
passing vacuously. Last control result (Yosys 0.67): exits 0 with the
fixture's `$_DLATCH_P_` cell named in `flow/build/synth-negctl.log`.

Mapped gate-level netlist (committed as `efuse_otp_ctrl.gl.v`), for
`gf180mcu_fd_sc_mcu7t5v0` at 32 x 8 (`synth-request.json` states `ROWS`, `COLS`,
`AW` explicitly):

```sh
rtl/regen-gl.sh           # rewrite rtl/efuse_otp_ctrl.gl.v with the pinned klt
rtl/regen-gl.sh --check   # regenerate to a temp file; non-zero if it differs
```

The script runs `klt synthesize` from the release in `signoff/klt-pin.txt`
(`uvx --from`, never a host-installed klt), needs `yosys` on `PATH` and the
`gf180mcuD` PDK under `PDK_ROOT` (default `~/.ciel`), and exits non-zero unless
klt's structural counts are zero (`latches`, `unexpected_latches`, `comb_loops`,
`multi_driven`) and the mapped netlist contains no latch cell. With klt 0.8.0 and
Yosys 0.67+post, two consecutive runs produce byte-identical netlists. The
netlist depends on the klt release and Yosys version, so a pin bump means
regenerating it and the item-1 attestation (`signoff/README.md`). klt writes
scratch under `rtl/.klt/` (gitignored).

## Sibling reuse decision

Searched the public gf180 canaries `gf180-trng`, `gf180-sram`, `gf180-riscv-soc`
and `gf180-fpga` (file trees, 2026-10-23) for an arm-then-strobe or pulse
sequencer and for cocotb/Yosys conventions. **Not adopted**: none holds such a
sequencer (`gf180-trng` has plain-Verilog testbenches and health-test logic
only; the others expose no comparable controller RTL), and none uses cocotb.
Conventions followed instead: flat `rtl/`, Icarus, Yosys `synth`.
The PDK's precompiled `gf180mcu_re_efuse` macros are not installed
(spec section 1.2) and are not reimplemented here.
